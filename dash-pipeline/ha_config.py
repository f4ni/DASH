import os
import json
import grpc
from p4.v1 import p4runtime_pb2
from p4.v1 import p4runtime_pb2_grpc

def clean_p4info_dict(d):
    """Recursively clean P4Info dict to remove unsupported values like 'LIST' match type."""
    if isinstance(d, dict):
        for k, v in d.items():
            if k == 'matchType' and v in ('LIST', 'RANGE_LIST'):
                # Replace unsupported match types with OPTIONAL/EXACT to pass validation
                d[k] = 'OPTIONAL' 
            else:
                clean_p4info_dict(v)
    elif isinstance(d, list):
        for item in d:
            clean_p4info_dict(item)

def configure_ha(port, role, mac="00:11:22:33:44:55", eni_id=1, scope_id=1, set_id=1):
    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = p4runtime_pb2_grpc.P4RuntimeStub(channel)
    
    # 1. Set Forwarding Pipeline Config
    p4info_path = "py_model/dash_pipeline.py_model/dash_pipeline_p4rt.json"
    if not os.path.exists(p4info_path):
        print(f"Error: {p4info_path} not found. Run 'make py-artifacts' first.")
        return

    request = p4runtime_pb2.SetForwardingPipelineConfigRequest()
    request.action = p4runtime_pb2.SetForwardingPipelineConfigRequest.VERIFY_AND_COMMIT
    request.device_id = 1
    
    with open(p4info_path, 'r') as f:
        p4info_dict = json.load(f)
        
    # FIX: Clean the dictionary of invalid enum values
    clean_p4info_dict(p4info_dict)

    from google.protobuf import json_format
    config = request.config
    try:
        json_format.ParseDict(p4info_dict, config.p4info)
    except Exception as e:
        print(f"Error parsing P4Info: {e}")
        # Proceeding might fail if server relies on config... 
        # But let's try to proceed if possible or exit.
        return
    
    try:
        stub.SetForwardingPipelineConfig(request)
        print(f"[{port}] Pipeline Configured.")
    except grpc.RpcError as e:
        print(f"[{port}] Config Failed: {e}")
        # Continue anyway, server might already be configured
        # return 

    # Helper to get IDs
    ids = build_p4_info_helper(p4info_path)
    
    # Simple helpers for ID lookup
    def get_table_id(name):
        return ids.get(name, 0)
    
    def get_action_id(t_name, a_name):
        return ids.get(t_name + ":actions", {}).get(a_name, 0)

    def get_field_id(t_name, m_name):
        for t in p4info_dict['tables']:
            if t['preamble']['name'] == t_name:
                for m in t['matchFields']:
                    if m['name'] == m_name:
                        return m['id']
        return 0
    
    def get_param_id(a_name, p_name):
        for a in p4info_dict['actions']:
            if a['preamble']['name'] == a_name:
                for p in a['params']:
                    if p['name'] == p_name:
                        return p['id']
        return 0

    updates = []
    
    print(f"Configuring {role}...")

    # ---------------------------------------------------------
    # 1. eni_ether_address_map: MAC -> ENI_ID
    # ---------------------------------------------------------
    t_name = "dash_ingress.eni_lookup_stage.eni_ether_address_map"
    entry = p4runtime_pb2.TableEntry()
    entry.table_id = get_table_id(t_name)
    
    match = entry.match.add()
    match.field_id = get_field_id(t_name, "meta.eni_addr")
    match.exact.value = bytes.fromhex(mac.replace(":",""))
    
    action = entry.action.action
    a_name = "dash_ingress.eni_lookup_stage.set_eni"
    action.action_id = get_action_id(t_name, a_name)
    
    param = action.params.add()
    param.param_id = get_param_id(a_name, "eni_id")
    param.value = eni_id.to_bytes(2, 'big')

    update = p4runtime_pb2.Update()
    update.type = p4runtime_pb2.Update.INSERT
    update.entity.table_entry.CopyFrom(entry)
    updates.append(update)

    # ---------------------------------------------------------
    # 2. eni: ENI_ID -> Attributes (including ha_scope_id)
    # ---------------------------------------------------------
    t_name = "dash_ingress.dash_eni_stage.eni"
    entry = p4runtime_pb2.TableEntry()
    entry.table_id = get_table_id(t_name)
    
    match = entry.match.add()
    match.field_id = get_field_id(t_name, "meta.eni_id")
    match.exact.value = eni_id.to_bytes(2, 'big')
    
    action = entry.action.action
    a_name = "dash_ingress.dash_eni_stage.set_eni_attrs"
    action.action_id = get_action_id(t_name, a_name)
    
    # Params
    for a in p4info_dict['actions']:
        if a['preamble']['name'] == a_name:
            for p in a['params']:
                val = 0
                if p['name'] == 'ha_scope_id':
                    val = scope_id
                elif p['name'] == 'admin_state':
                    val = 1
                elif p['name'] == 'vnet_id':
                    val = 1
                # flow_table_id for conntrack check?
                elif p['name'] == 'flow_table_id':
                    val = 1
                
                width = p['bitwidth']
                byte_len = (width + 7) // 8
                param = action.params.add()
                param.param_id = p['id']
                param.value = val.to_bytes(byte_len, 'big')

    update = p4runtime_pb2.Update()
    update.type = p4runtime_pb2.Update.INSERT
    update.entity.table_entry.CopyFrom(entry)
    updates.append(update)

    # ---------------------------------------------------------
    # 3. ha_scope: Scope ID -> Role, Set ID
    # ---------------------------------------------------------
    t_name = "dash_ingress.ha_stage.ha_scope"
    entry = p4runtime_pb2.TableEntry()
    entry.table_id = get_table_id(t_name)
    
    match = entry.match.add()
    match.field_id = get_field_id(t_name, "meta.ha.ha_scope_id")
    match.exact.value = scope_id.to_bytes(2, 'big')
    
    action = entry.action.action
    a_name = "dash_ingress.ha_stage.set_ha_scope_attr"
    action.action_id = get_action_id(t_name, a_name)
    
    role_val = 1 if role == 'active' else 2 # 1=Active, 2=Standby
    
    for a in p4info_dict['actions']:
        if a['preamble']['name'] == a_name:
            for p in a['params']:
                val = 0
                if p['name'] == 'ha_set_id':
                    val = set_id
                elif p['name'] == 'dash_ha_role':
                    val = role_val
                
                width = p['bitwidth']
                byte_len = (width + 7) // 8
                param = action.params.add()
                param.param_id = p['id']
                param.value = val.to_bytes(byte_len, 'big')

    update = p4runtime_pb2.Update()
    update.type = p4runtime_pb2.Update.INSERT
    update.entity.table_entry.CopyFrom(entry)
    updates.append(update)

    # ---------------------------------------------------------
    # 4. ha_set: Set ID -> Peer IP etc
    # ---------------------------------------------------------
    t_name = "dash_ingress.ha_stage.ha_set"
    entry = p4runtime_pb2.TableEntry()
    entry.table_id = get_table_id(t_name)
    
    match = entry.match.add()
    match.field_id = get_field_id(t_name, "meta.ha.ha_set_id")
    match.exact.value = set_id.to_bytes(2, 'big')
    
    action = entry.action.action
    a_name = "dash_ingress.ha_stage.set_ha_set_attr"
    action.action_id = get_action_id(t_name, a_name)
    
    for a in p4info_dict['actions']:
        if a['preamble']['name'] == a_name:
            for p in a['params']:
                val = 0
                # Using dummy IPs. 
                if p['name'] == 'peer_ip':
                     # 10.0.0.2 for Active's peer, 10.0.0.1 for Standby's peer
                     val = 0x0A000002 if role == 'active' else 0x0A000001
                
                width = p['bitwidth']
                byte_len = (width + 7) // 8
                param = action.params.add()
                param.param_id = p['id']
                param.value = val.to_bytes(byte_len, 'big')

    update = p4runtime_pb2.Update()
    update.type = p4runtime_pb2.Update.INSERT
    update.entity.table_entry.CopyFrom(entry)
    updates.append(update)

    # ---------------------------------------------------------
    # 5. SIMULATE DPAPP FLOW CREATION (Optional/Test Mode)
    # Insert a Conntrack Entry to simulate a flow being "Created"
    # This allows testing HA generation without actually running DPAPP.
    # ---------------------------------------------------------
    if role == 'active':
        print("Injecting Conntrack Entry (FLOW_CREATED) to simulate DPAPP...")
        # We need to target the Conntrack table.
        # Check actual table name in dash_pipeline.py or p4info.
        # Likely "dash_ingress.conntrack_lookup_stage.conntrack"
        t_name = "dash_ingress.conntrack_lookup_stage.conntrack"
        
        # If table key is complex (Five Tuple), we must construct it matching our test packet.
        # Test Packet: src=1.1.1.1, dst=2.2.2.2, sport=100, dport=200, proto=6 (TCP)
        # ENI ID = 1 (we set it above)
        # VNET ID = 1 (we set it in ENI attrs)
        
        # Key fields likely: eni_id, vnet_id, src_ip, dst_ip, src_port, dst_port, protocol...
        # Need to check p4info or dash_pipeline.py for EXACT keys.
        # dash_pipeline.py: 
        #   "flow_key.eni_mac": (EXACT), ... ?
        #   Wait, flow key is struct `flow_key_t`.
        #   py_model `Table` definition for `conntrack`:
        #   key={"meta.flow_key": (EXACT, ...)}
        #   Wait, python model often flattens keys or uses struct binding.
        #   Let's check p4info for "conntrack" keys.
        
        t_id = get_table_id(t_name)
        if t_id:
            entry = p4runtime_pb2.TableEntry()
            entry.table_id = t_id
            
            # We assume keys match the P4Info order/names.
            # dash_headers.py: flow_key_t definition.
            # eni_mac, vnet_id, src_ip, dst_ip, src_port, dst_port, ip_proto ...
            
            def add_match(name, val, width_bytes):
                m = entry.match.add()
                m.field_id = get_field_id(t_name, name)
                m.exact.value = val.to_bytes(width_bytes, 'big')

            # We'll use get_field_id to find matches.
            # Common names from dash_pipeline.py or dash_headers.py mappings
            # Note: py_model likely prefixes with "meta.flow_key."
            
            # 1.1.1.1 = 0x01010101
            # 2.2.2.2 = 0x02020202
            
            # We try to set all keys.
            # NOTE: If we miss keys, P4Runtime insert might fail.
            # But we'll try best effor based on standard keys.
            
            # Helper to find keys
            keys = []
            for t in p4info_dict['tables']:
                if t['preamble']['name'] == t_name:
                    keys = t['matchFields']
                    break
                    
            for k in keys:
                kname = k['name']
                val = 0
                width = k['bitwidth']
                wbytes = (width+7)//8
                
                if "src_ip" in kname: val = 0x01010101
                elif "dst_ip" in kname: val = 0x02020202
                elif "src_port" in kname: val = 100
                elif "dst_port" in kname: val = 200
                elif "protocol" in kname or "ip_proto" in kname: val = 6
                elif "eni_id" in kname: val = 1 # ? flow_key usually has eni_mac or vnet_id. 
                elif "vnet_id" in kname: val = 1
                elif "eni_mac" in kname: val = int(mac.replace(":",""), 16)
                
                m = entry.match.add()
                m.field_id = k['id']
                m.exact.value = val.to_bytes(wbytes, 'big')

            # ACTION: set_flow_state? OR simply strict `set_flow_entry`.
            # We need to set state to FLOW_CREATED (1).
            # And action should probably be one that sets flow details.
            # We'll pick the first available action or specific one.
            # `conntrack` table usually has `set_flow_entry` action.
            
            a_name = "dash_ingress.conntrack_lookup_stage.set_flow_entry"
            if get_action_id(t_name, a_name):
                 action = entry.action.action
                 action.action_id = get_action_id(t_name, a_name)
                 
                 # Params: flow_sync_state, etc.
                 # Need to find params and set state=1
                 for a in p4info_dict['actions']:
                    if a['preamble']['name'] == a_name:
                        for p in a['params']:
                             val = 0
                             if "flow_sync_state" in p['name']:
                                 val = 1 # FLOW_CREATED
                             
                             # Set dummy values for others
                             width = p['bitwidth']
                             wbytes = (width+7)//8
                             param = action.params.add()
                             param.param_id = p['id']
                             param.value = val.to_bytes(wbytes, 'big')
                 
                 print("    Added Flow Entry with State=FLOW_CREATED")
                 update = p4runtime_pb2.Update()
                 update.type = p4runtime_pb2.Update.INSERT
                 update.entity.table_entry.CopyFrom(entry)
                 updates.append(update)
            else:
                 print(f"    Warning: Could not find action {a_name}")

    
    # ---------------------------------------------------------
    # SEND WRITE REQUEST
    # ---------------------------------------------------------
    req = p4runtime_pb2.WriteRequest()
    req.device_id = 1
    req.updates.extend(updates)
    
    try:
        stub.Write(req)
        print(f"[{port}] Tables Configured successfully for role: {role.upper()}")
    except grpc.RpcError as e:
        # Ignore already exists
        if e.code() == grpc.StatusCode.ALREADY_EXISTS:
             print(f"[{port}] Configuration already exists.")
        else:
             print(f"[{port}] Write Failed: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9559)
    parser.add_argument("--role", type=str, required=True, choices=['active', 'standby'])
    args = parser.parse_args()
    
    configure_ha(args.port, args.role)

