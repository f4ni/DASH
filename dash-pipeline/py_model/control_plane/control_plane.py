import builtins
from py_model.libs.__utils import *
from py_model.libs.__id_map import *
from py_model.libs.__table import *
from py_model.libs.__obj_classes import *
from py_model.data_plane.dash_pipeline import *

class InsertRequest:
    class Value:
        class Ternary:
            value : str
            mask  : str
            def __init__(self):
                self.value = ""
                self.mask = ""
        
        class LPM:
            value : str
            prefix_len : int
            def __init__(self):
                self.value = ""
                self.prefix_len = 0

        class Range:
            low : str
            high  : str
            def __init__(self):
                self.low = ""
                self.high = ""

        exact   : str
        ternary : Ternary
        prefix  : LPM
        range   : Range
        ternary_list : list[Ternary]
        range_list : list[Range]
        
        def __init__(self):
            self.exact = ""
            self.ternary = InsertRequest.Value.Ternary()
            self.prefix = InsertRequest.Value.LPM()
            self.range = InsertRequest.Value.Range()
            self.ternary_list = []
            self.range_list = []

    table    : int
    values   : list[Value]
    action   : int
    params   : list[str]
    priority : int
    
    def __init__(self):
        self.table = 0
        self.values = []
        self.action = 0
        self.params = []
        self.priority = 0


# Function to get table name by ID
def get_table_name(table_id: int):
    return table_ids.get(table_id, "unknown")

# Function to get action name by ID
def get_action_name(action_id: int) -> str:
    return action_ids.get(action_id, "unknown")

def resolve_action_name(name: str, ctx=None):
    if ctx is None:
        ctx = globals()
    obj = ctx

    parts = name.split(".")
    # handle "dash_ingress.something" style
    if len(parts) > 2:
        parts = parts[1:]

    for i, part in enumerate(parts, start=1):
        try:
            if isinstance(obj, dict):
                obj = obj[part]
            else:
                obj = getattr(obj, part)
        except (KeyError, AttributeError) as e:
            py_log("info", f"ERROR: cannot resolve '{part}' - {e}")
            return None
    return obj

def resolve_table_name(name: str, ctx=None):
    if ctx is None:
        ctx = globals()

    if name in table_objs:
        obj = table_objs[name]
        return obj
    else:
        parts = name.split(".")

        obj = ctx
        for i, part in enumerate(parts, start=1):
            try:
                if isinstance(obj, dict):
                    obj = obj[part]
                else:
                    obj = getattr(obj, part)
            except (KeyError, AttributeError):
                # fallback: try resolving from global context if exists
                if part in globals():
                    obj = globals()[part]
                else:
                    return None
    return obj

def populate_table_entry(insertRequest: InsertRequest, key_format: list):
    entry = Entry()
    entry.values = []

    for idx, val in builtins.enumerate(insertRequest.values):
        if idx >= len(key_format):
            py_log("info", f"Skipping index {idx}, no matching key format.")
            continue

        match_type = key_format[idx]

        if match_type is EXACT:
            entry.values.append(val.exact)

        elif match_type is TERNARY:
            ternary = Entry.Ternary()
            try:
                ternary.value = int(val.ternary.value, 16)
                ternary.mask = int(val.ternary.mask, 16)
            except Exception as e:
                py_log("error", f"TERNARY conversion error: {e}")
                continue
            entry.values.append(ternary)

        elif match_type is LIST:
            ternary_list = []
            for t in val.ternary_list:
                tern = Entry.Ternary()
                try:
                    tern.value = int(t.value, 16)
                    tern.mask = t.mask
                except Exception as e:
                    py_log("error", f"LIST item conversion error: {e}")
                    continue
                ternary_list.append(tern)
            entry.values.append(ternary_list)
        elif match_type is RANGE:
            rng = Entry.Range()
            try:
                rng.low = int(val.range.low, 16)
                rng.high = int(val.range.high, 16)
            except Exception as e:
                py_log("error", f"RANGE conversion error: {e}")
                continue
            entry.values.append(rng)
        elif match_type is RANGE_LIST:
            rng_list = []
            for r in val.range_list:
                rng = Entry.Range()
                try:
                    rng.low = int(r.low, 16)
                    rng.high = int(r.high, 16)
                except Exception as e:
                    py_log("error", f"RANGE_LIST item conversion error: {e}")
                    continue
                rng_list.append(rng)
            entry.values.append(rng_list)
        elif match_type is LPM:
            lpm = Entry.LPM()
            lpm.value = val.prefix.value
            lpm.prefix_len = val.prefix.prefix_len
            entry.values.append(lpm)

    action_id = insertRequest.action
    if action_id is not None:
        action_name = get_action_name(action_id)
        py_log(f"Action: {action_name}")
        action_obj = resolve_action_name(action_name)
        if not action_obj:
            py_log("info", f"Could not resolve action name: {action_name}")
            return None
        entry.action = action_obj

        entry.params = []
        for param_str in insertRequest.params:
            entry.params.append(param_str)

    entry.priority = insertRequest.priority
    return entry

def table_insert_api(insertRequest: InsertRequest, req_type):
    table_id = insertRequest.table
    table_name = get_table_name(table_id)
    if table_name == "unknown":
        return RETURN_FAILURE

    table = resolve_table_name(table_name)
    if not table:
        return RETURN_FAILURE

    key_values = list(table.key.values())
    if not key_values:
        return RETURN_FAILURE

    entry = populate_table_entry(insertRequest, key_values)
    if not entry:
        return RETURN_FAILURE

    if req_type == 'INSERT':
        for e in table.entries:
            if e.values == entry.values:
                py_log("info", "Match entry exists, use MODIFY if you wish to change action")
                return RETURN_FAILURE
        ret = table.insert(entry)
    elif req_type == 'MODIFY':
        ret = table.update(entry)
    elif req_type == 'DELETE':
        ret = table.delete(entry)
        if ret == RETURN_SUCCESS:
            py_log("info", f"Entry deleted from Table {table_name}")
        else:
            py_log("info", f"Failed deleting the entry from Table {table_name}")
    else:
        py_log("info", f"Unknown operation type: {req_type}")
        return RETURN_FAILURE

    return RETURN_SUCCESS

def normalize_table_entry(entry: dict) -> dict:
    normalized = dict(entry)  # shallow copy

    # Sort match fields
    if "match" in normalized:
        normalized["match"] = sorted(
            normalized["match"], key=lambda m: m.get("fieldId", 0)
        )

    # Sort params inside action
    if "action" in normalized and "action" in normalized["action"]:
        action_data = dict(normalized["action"]["action"])
        if "params" in action_data:
            action_data["params"] = sorted(
                action_data["params"], key=lambda p: p.get("paramId", 0)
            )
        normalized["action"]["action"] = action_data

    return normalized

def parse_insert_request(json_obj):
    insertRequest = InsertRequest()

    # Extract table entry information
    req_type = json_obj.get("type", {})
    py_log(None, f"\nReceived request: {req_type}")
    py_log(None, "=" * 25)

    table_entry = json_obj.get("entity", {}).get("tableEntry", {})

    table_entry = normalize_table_entry(table_entry)

    # Table ID
    insertRequest.table = table_entry.get("tableId", [])
    table_name = get_table_name(insertRequest.table)

    table = resolve_table_name(table_name)

    keys = list(table.key.keys())
    py_log("info", f"Table {table_name}")

    # Process match fields
    insertRequest.values = []
    match_fields = table_entry.get("match", [])
    py_log(None, "Match Fields:")
    for idx, match_field in builtins.enumerate(match_fields):
        fieldId = match_field["fieldId"] - 1

        value = InsertRequest.Value()

        if "exact" in match_field:
            value.exact = get_hex_value(match_field["exact"]["value"])
            py_log(None, f"* {keys[fieldId]}: Exact : {value.exact}")

        if "ternary" in match_field:
            value.ternary = InsertRequest.Value.Ternary()
            value.ternary.value = get_hex_value(match_field["ternary"]["value"])
            value.ternary.mask = get_hex_value(match_field["ternary"]["mask"])
            value.ternary_list.append(value.ternary)
            py_log(None, f"* {keys[fieldId]}: TERNARY : {value.ternary.value} && {value.ternary.mask}")

        if "optional" in match_field:
            if keys[fieldId] == 'meta.dst_ip_addr' or keys[fieldId] == 'meta.src_ip_addr' or keys[fieldId] == 'meta.ip_protocol':
                value.ternary = InsertRequest.Value.Ternary()
                hex_val = get_hex_value(match_field["optional"]["value"])
                value.ternary.value = hex_val
                decimal_val = int(hex_val, 16)
                num_bytes = (decimal_val.bit_length() + 7) // 8  # Round up to the nearest # of bytes
                value.ternary.mask = (1 << (num_bytes * 8)) - 1  # Same as repeating 0xFF per byte
                value.ternary_list.append(value.ternary)
                py_log(None, f"* {keys[fieldId]}: TERNARY - LIST : {value.ternary.value} && {hex(value.ternary.mask)}")
            elif keys[fieldId] == 'meta.src_l4_port' or keys[fieldId] == 'meta.dst_l4_port':
                value.range = InsertRequest.Value.Range()
                hex_val = get_hex_value(match_field["optional"]["value"])
                value.range.low = hex_val
                value.range.high = hex_val
                value.range_list.append(value.range)
                py_log(None, f"* {keys[fieldId]}: RANGE - LIST: {value.range.low} -> {value.range.high}")

        if "lpm" in match_field:
            value.prefix = InsertRequest.Value.LPM()
            value.prefix.value = get_hex_value(match_field["lpm"]["value"])
            value.prefix.prefix_len = match_field["lpm"]["prefixLen"]
            meta.dst_ip_addr = int(value.prefix.value, 16)      # for lookup during read request
            py_log(None, f"* {keys[fieldId]}: LPM : {value.prefix.value} : {hex(value.prefix.prefix_len)}")

        if "range" in match_field:
            value.range = InsertRequest.Value.Range()
            value.range.low = get_hex_value(match_field["range"]["low"])
            value.range.high = get_hex_value(match_field["range"]["high"])
            py_log(None, f"* {keys[fieldId]}: Range: {value.range.low} -> {value.range.high}")

        insertRequest.values.append(value)

    insertRequest.priority = table_entry.get("priority", 0)
    py_log("info", f"Priority: {insertRequest.priority}")

    # Action
    action_data = table_entry.get("action", {}).get("action", {})
    insertRequest.action = action_data.get("actionId", None)

    if insertRequest.action is not None:
        action_name = get_action_name(insertRequest.action)

        # Parameters
        insertRequest.params = []
        for param in action_data.get('params', []):
            value = param.get("value")
            hex_val = 0
            if value is not None:
                hex_val = get_hex_value(param["value"])
                hex_val = int(hex_val, 16)
            else:
                hex_val = 0
            insertRequest.params.append(hex_val)
        # py_log("info", f"Action {insertRequest.action} : {action_name} {insertRequest.params}\n")

    return insertRequest
