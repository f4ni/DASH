import base64
import hashlib
from py_model.libs.__utils import *
from py_model.libs.__table import *


# Fixed widths (for fields that never change)
BASE_FIELD_WIDTHS = {
    1: 6,   # eni_mac
    2: 2,   # vnet_id
    5: 2,   # src_port
    6: 2,   # dst_port
    7: 1,   # ip_proto
    8: 1,   # is_ip_v6
}

def int_to_base64_fixed(value: int, width_bytes: int):
    return base64.b64encode(
        value.to_bytes(width_bytes, "big")
    ).decode()

def encode_match_value_fixed(field_id: int, value, width: int):

    if isinstance(value, int):
        return {
            "fieldId": field_id,
            "exact": {
                "value": int_to_base64_fixed(value, width)
            }
        }

    if isinstance(value, Entry.LPM):
        return {
            "fieldId": field_id,
            "lpm": {
                "value": int_to_base64_fixed(value.value, width),
                "prefixLen": value.prefix_len
            }
        }

    if isinstance(value, Entry.Ternary):
        return {
            "fieldId": field_id,
            "ternary": {
                "value": int_to_base64_fixed(value.value, width),
                "mask": int_to_base64_fixed(value.mask, width)
            }
        }

    if isinstance(value, Entry.Range):
        return {
            "fieldId": field_id,
            "range": {
                "low": int_to_base64_fixed(value.low, width),
                "high": int_to_base64_fixed(value.high, width)
            }
        }

    raise TypeError(f"Unsupported match type: {type(value)}")

def extract_match(entry):
    match = []

    is_ipv6 = entry.values[7]  # fieldId 8

    for idx, value in enumerate(entry.values):
        field_id = idx + 1

        # dynamic width for src_ip and dst_ip
        if field_id in (3, 4):   # src_ip or dst_ip
            width = 16 if is_ipv6 == 1 else 4
        else:
            width = BASE_FIELD_WIDTHS[field_id]

        match.append(encode_match_value_fixed(field_id, value, width))

    return match

def populate_params():
    params = []

    params.append(0)
    params.append(meta.direction)
    params.append(meta.routing_actions)
    params.append(meta.meter_class)
    params.append(0)
    params.append(meta.flow_sync_state)

    params.append(0)
    params.append(0)
    params.append(0)
    params.append(0)
    params.append(0)
    params.append(0)
    params.append(0)
    params.append(0)

    params.append(meta.u0_encap_data.vni)
    params.append(meta.u0_encap_data.underlay_sip)
    params.append(meta.u0_encap_data.underlay_dip)
    params.append(meta.u0_encap_data.underlay_smac)
    params.append(meta.u0_encap_data.underlay_dmac)
    params.append(meta.u0_encap_data.dash_encapsulation)

    params.append(meta.u1_encap_data.vni)
    params.append(meta.u1_encap_data.underlay_sip)
    params.append(meta.u1_encap_data.underlay_dip)
    params.append(meta.u1_encap_data.underlay_smac)
    params.append(meta.u1_encap_data.underlay_dmac)
    params.append(meta.u1_encap_data.dash_encapsulation)

    params.append(meta.overlay_data.dmac)
    params.append(meta.overlay_data.sip)
    params.append(meta.overlay_data.dip)
    params.append(meta.overlay_data.sip_mask)
    params.append(meta.overlay_data.dip_mask)
    params.append(meta.overlay_data.is_ipv6)

    params.append(0)
    params.append(0)

    return params

def populate_entry():
    entry = Entry()

    entry.values.append(hdr.flow_key.eni_mac) 
    entry.values.append(hdr.flow_key.vnet_id) 
    entry.values.append(hdr.flow_key.src_ip) 
    entry.values.append(hdr.flow_key.dst_ip) 
    entry.values.append(hdr.flow_key.src_port) 
    entry.values.append(hdr.flow_key.dst_port) 
    entry.values.append(hdr.flow_key.ip_proto) 
    entry.values.append(hdr.flow_key.is_ip_v6) 

    obj = action_objs.get("conntrack_lookup_stage.set_flow_entry_attr")
    method = obj[0] if isinstance(obj, tuple) else obj
    func = method.__func__ if isinstance(method, staticmethod) else method

    entry.action = func
    entry.params = populate_params()

    entry.priority = 0

    match = extract_match(entry)

    hash = hashlib.sha256(str(match).encode()).hexdigest()

    return hash, entry
