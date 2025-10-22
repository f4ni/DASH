#!/usr/bin/env python3
"""
Optimized generator for py_p4rt.json from dash_py_model in-memory model.
- Caches expensive reflection (enum/member lookups, annotation width reads)
- Uses comprehensions where appropriate
- Simplifies/clarifies structured-annotation extraction
- Keeps behavior compatible with your original code
"""

import os
import re
import sys
import enum
import json
import base64
import inspect
from collections import OrderedDict
from functools import lru_cache
from typing import Annotated, Optional, get_origin, get_args, get_type_hints as get_annotations

from call_graph import build_call_graph
from cg import generate_callgraph
from acg import generate_tablegraph
from p4ir_gen import make_ir

from lib.__table import *
from lib.__id_map import *
from lib.__jsonize import *
from lib.__counters import *
from dash_py_model import *

# Local references for speed
_isfunction = inspect.isfunction
_getmembers = inspect.getmembers
_issubclass = issubclass
_isclass = inspect.isclass
_int_types = (int,)
_enum_types = (enum.IntEnum, enum.IntFlag)

project_dir = "./pmv2"
func_set = []
func_chain = []
act_alias_names = []
table_chain = []
tab_alias_names = []

class SafeEncoder(json.JSONEncoder):
    def default(self, o):
        # enum members -> their value
        if isinstance(o, enum.Enum):
            return o.value
        # enum types -> mapping name->value
        if inspect.isclass(o) and issubclass(o, enum.Enum):
            return {e.name: e.value for e in o}
        # callables -> name
        if callable(o):
            return getattr(o, "__name__", str(o))
        return super().default(o)

def is_int_str(val: str) -> bool:
    if not isinstance(val, str):
        return False
    return val.lstrip("-").isdigit()

def format_scalar(val):
    if isinstance(val, str):
        return json.dumps(val)
    elif isinstance(val, bool):
        return "true" if val else "false"
    return str(val)

def to_snake_case(name):
    # camelCase or PascalCase → snake_case
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def base64_to_escaped(b64_str):
    # Decode base64 to bytes
    decoded_bytes = base64.b64decode(b64_str)
    # Convert each byte to \ooo (octal) escaped format
    escaped = ''.join(f'\\{byte:03o}' for byte in decoded_bytes)
    return escaped

def dict_to_textproto(d: dict, indent: int = 0, parent_key: str = "") -> str:
    """Recursively dumps a dict/list into Protobuf text format style."""
    lines = []
    pad = " " * indent

    if isinstance(d, dict):
        for key, value in d.items():
            key = to_snake_case(key)

            # Special-case for serializable_enums (map field)
            if key == "serializable_enums" and isinstance(value, dict):
                for map_key, map_val in value.items():
                    lines.append(f"{pad}{key} {{")
                    lines.append(f"{pad}  key: \"{map_key}\"")
                    lines.append(f"{pad}  value {{")
                    lines.append(dict_to_textproto(map_val, indent + 4))
                    lines.append(f"{pad}  }}")
                    lines.append(f"{pad}}}")
            elif isinstance(value, dict):
                lines.append(f"{pad}{key} {{")
                lines.append(dict_to_textproto(value, indent + 2))
                lines.append(f"{pad}}}")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{pad}{key} {{")
                        lines.append(dict_to_textproto(item, indent + 2))
                        lines.append(f"{pad}}}")
                    else:
                        lines.append(f"{pad}{key}: {format_scalar(item)}")
            else:
                if key != "unit" and key != "size" and key != "int64_value" and key != "match_type" and value != "DEFAULT_ONLY":
                    value = format_scalar(value)
                if value == "LIST" or value == "RANGE_LIST":
                    value = "OPTIONAL"
                if key == 'value':
                    value = base64_to_escaped(value)
                    value = f"\"{value}\""
                lines.append(f"{pad}{key}: {value}")

    elif isinstance(d, list):
        for item in d:
            if isinstance(item, dict):
                lines.append(f"{pad}{{")
                lines.append(dict_to_textproto(item, indent + 2))
                lines.append(f"{pad}}}")
            else:
                lines.append(f"{pad}{format_scalar(item)}")

    return "\n".join(lines)

def find_by_function_name(func_name: str) -> str | None:
    input_parts = func_name.split(".")
    best_match = None
    best_len = 0

    for full_name in func_chain:
        full_parts = full_name.split(".")
        min_len = min(len(input_parts), len(full_parts))
        match_len = 0
        for i in range(1, min_len + 1):
            if input_parts[-i] == full_parts[-i]:
                match_len += 1
            else:
                break
        if match_len > best_len:
            best_len = match_len
            best_match = full_name

    return best_match

def find_by_table_name(table_name: str) -> str | None:
    input_parts = table_name.split(".")
    best_match = None
    best_len = 0

    for full_name in table_chain:
        full_parts = full_name.split(".")
        min_len = min(len(input_parts), len(full_parts))
        match_len = 0
        for i in range(1, min_len + 1):
            if input_parts[-i] == full_parts[-i]:
                match_len += 1
            else:
                break
        if match_len > best_len:
            best_len = match_len
            best_match = full_name

    return best_match

@lru_cache(maxsize=1024)
def _read_width(k: str) -> Optional[int]:
    """
    Read bitwidth for a dotted key like "Container.field.subfield".
    Caches results because this uses runtime type introspection.
    """
    try:
        tokens = k.split(".")
        if not tokens:
            return None
        # First token is a global name
        root_name, *rest = tokens
        container = globals().get(root_name)
        if container is None:
            return None

        # iterate through annotation types
        container_type = type(container)
        var_name = rest[0] if rest else None
        for token in rest[1:]:
            anns = get_annotations(container_type) or {}
            container_type = anns.get(var_name)
            var_name = token
            if container_type is None:
                return None

        anns = get_annotations(container_type) or {}
        ann = anns.get(var_name)
        if ann is None:
            return None

        if get_origin(ann) is Annotated:
            args = get_args(ann)
            # metadata usually at args[2] in your pattern
            if len(args) >= 3 and isinstance(args[2], dict):
                # assume 'bitwidth' or direct width is in metadata
                return args[2].get("bitwidth") or args[2].get("width") or None

            # numeric second arg for Annotated[int, <width>]
            if len(args) > 1 and isinstance(args[1], int):
                return args[1]

        # If annotation is an enum class, try its __bitwidth__
        if _isclass(ann) and issubclass(ann, _enum_types):
            return getattr(ann, "__bitwidth__", None)

        # fallback: if it's a raw int annotation assume 32
        if ann is int:
            return 32

    except Exception:
        # Do not crash on unexpected types; caller should handle None.
        return None

def _strip_none(d: dict) -> Optional[dict]:
    """Return dict with keys whose values are not None; or None if empty."""
    out = {k: v for k, v in (d or {}).items() if v is not None}
    return out or None

def _get_str_annos_for_key(api_hints: dict, k: str) -> Optional[dict]:
    """Extract non-None attributes from a SaiVal-like object stored in api_hints[k]."""
    sai_val = api_hints.get(k)
    if sai_val is None:
        return None
    sai_dict = getattr(sai_val, "__dict__", None)
    if not sai_dict:
        return None
    return _strip_none(sai_dict)

def _get_str_annos_for_table(sai_table) -> Optional[dict]:
    """Return a dict of peri-table annotation attributes (filtering functions and keys)."""
    if sai_table is None:
        return None
    sai_dict = getattr(sai_table, "__dict__", None)
    if not sai_dict:
        return None
    keyset = set(getattr(sai_table, "key", {}))
    filtered = {
        k: v
        for k, v in sai_dict.items()
        if v is not None and not isinstance(v, staticmethod) and not _isfunction(v) and k not in keyset
    }
    return filtered or None

def _make_str_annos_node(str_annos: dict, kind: int):
    """
    Turn a dict of structured annotations into the JSON node shape expected by P4RT.
    kind: 0=table, 1=saival/action param, 2=counter
    """
    if not str_annos:
        return None

    kv_pairs = []
    if kind == 0:  # SaiTable
        # "ignored" is special-cased in original code
        if "ignored" in str_annos:
            kv_pairs.append({"key": "ignored", "value": {"stringValue": str(str_annos["ignored"])}})
        else:
            for key, value in str_annos.items():
                val_type = "int64Value" if key == "order" else "stringValue"
                kv_pairs.append({"key": key, "value": {val_type: str(value)}})
        name = "SaiTable"
    elif kind == 2:  # SaiCounter
        name = "SaiCounter"
        for key, value in str_annos.items():
            # booleans should be expressed as strings for compatibility with original output
            kv_pairs.append({"key": key, "value": {"stringValue": str(value)}})
    else:  # SaiVal or action param
        name = "SaiVal"
        for key, value in str_annos.items():
            kv_pairs.append({"key": key, "value": {"stringValue": str(value)}})

    return [{"name": name, "kvPairList": {"kvPairs": kv_pairs}}]

def _extract_annotation_info(k: str, anno):
    """
    Returns (bitwidth:int or None, str_annos:dict or None).
    Handles Annotated[...] patterns, enums, and plain int.
    """
    # Annotated[T, meta-or-width, opt-dict]
    if get_origin(anno) is Annotated:
        args = get_args(anno)
        base = args[0]
        # If args[1] is dict treat it as metadata
        maybe_width = None
        maybe_dict = None
        if len(args) > 1:
            if isinstance(args[1], dict):
                maybe_dict = args[1]
            elif isinstance(args[1], int):
                maybe_width = args[1]
        if len(args) > 2 and isinstance(args[2], dict):
            maybe_dict = args[2]

        # enums -> bitwidth from enum
        if _isclass(base) and issubclass(base, _enum_types):
            bw = getattr(base, "__bitwidth__", 16)
            # If user supplied an override width in metadata or second arg, prefer it
            return maybe_width or bw, maybe_dict

        if base is int:
            return maybe_width or 32, maybe_dict

        raise TypeError(f"Unsupported base type for param '{k}': {base}")

    # plain enum class
    if inspect.isclass(anno) and issubclass(anno, _enum_types):
        return getattr(anno, "__bitwidth__", 16), None

    # plain int annotation
    if anno is int:
        return 32, None

    raise TypeError(f"Unsupported annotation type for param '{k}': {anno}")

@lru_cache(maxsize=256)
def get_dash_enum_members(e):
    """Return a list of (name, enum-member) sorted by numeric value."""
    members = [(name, val) for name, val in _getmembers(e) if not name.startswith("_") and isinstance(val, e)]
    members.sort(key=lambda item: int(item[1]))
    return members

def make_enum_node(enum_cls):
    """Build the enum representation node used in typeInfo.serializableEnums."""
    enum_node = OrderedDict()
    bitwidth = getattr(enum_cls, "__bitwidth__", 16)
    enum_node["underlyingType"] = {"bitwidth": bitwidth}

    members_node = []
    members = get_dash_enum_members(enum_cls)

    # If IntFlag and has NONE member, ensure it's first (preserves original behavior)
    if issubclass(enum_cls, enum.IntFlag) and hasattr(enum_cls, "NONE"):
        members = [m for m in members if m[0] != "NONE"]
        members.insert(0, ("NONE", getattr(enum_cls, "NONE")))

    bytes_needed = (bitwidth + 7) // 8
    for name, member in members:
        int_value = int(member)
        # encode to big-endian with sufficient bytes
        b64_value = base64.b64encode(int_value.to_bytes(bytes_needed, "big", signed=False)).decode("ascii")
        members_node.append(OrderedDict([("name", name), ("value", b64_value)]))

    enum_node["members"] = members_node
    return enum_node

@lru_cache(maxsize=1)
def get_dash_enum_list():
    """Return list of enum classes in current module that are IntEnum/IntFlag subclasses."""
    class_list = _getmembers(sys.modules[__name__], inspect.isclass)
    return [
        cls
        for name, cls in class_list
        if not name.startswith("_")
        and inspect.isclass(cls)
        and issubclass(cls, _enum_types)
        and cls not in _enum_types
        and name not in ("BufferFlags",)
    ]

def make_table_node(table: Table, table_name: str, tid: int):
    """Construct table JSON node from Table instance."""
    table_node = OrderedDict()
    global tab_alias_names

    alias_name = table_name.rsplit(".", 1)[-1]
    if alias_name in tab_alias_names:
        parts = table_name.split(".")
        if len(parts) >= 2:
            alias_name = ".".join(parts[-2:])
        i = 3
        while alias_name in tab_alias_names and i <= len(parts):
            alias_name = ".".join(parts[-i:])
            i += 1

    tab_alias_names.append(alias_name)

    preamble_node = OrderedDict(id=tid, name=table_name, alias=alias_name)

    str_annos = _get_str_annos_for_table(table.sai_table)
    if str_annos:
        preamble_node["structuredAnnotations"] = _make_str_annos_node(str_annos, 0)

    table_node["preamble"] = preamble_node

    match_fields = []
    for mf_id, k in enumerate(table.key, start=1):
        mf = OrderedDict(id=mf_id, name=str(k), bitwidth=_read_width(k), matchType=table.key[k].__name__,)
        mf_str_annos = _get_str_annos_for_key(table.sai_val, k)
        if mf_str_annos:
            mf["structuredAnnotations"] = _make_str_annos_node(mf_str_annos, 1)
        match_fields.append(mf)

    table_node["matchFields"] = match_fields

    # actions
    action_refs = []

    def_act = 0

    def_act = table.default_action
    if def_act is not None:
        func, hints = def_act if isinstance(def_act, tuple) else (def_act, {})
        def_act = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))

        # if def_act not in func_set:
        is_class_method = next((flag for name, flag in func_set if name == def_act), False)
        if def_act not in [n for n, _ in func_set] or is_class_method:
            def_act = find_by_function_name(def_act) or def_act

        def_act_id = gen_symbol_id(def_act, ACTION)

    const_def_act = table.const_default_action
    if const_def_act is not None:
        func, hints = const_def_act if isinstance(const_def_act, tuple) else (const_def_act, {})
        const_def_act = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))

        # if const_def_act not in func_set:
        is_class_method = next((flag for name, flag in func_set if name == const_def_act), False)
        if const_def_act not in [n for n, _ in func_set] or is_class_method:
            const_def_act = find_by_function_name(const_def_act) or const_def_act

        def_act_id = gen_symbol_id(const_def_act, ACTION)

    # def_act = table.const_default_action_id is not None or table.default_action_id is not None

    # compute def_hint only once
    def_hint = any(isinstance(a, tuple) and a[1] for a in table.actions)

    for action in table.actions:
        func, hints = action if isinstance(action, tuple) else (action, {})
        act_name = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))

        print(f"\nProcessing action: {act_name}")

        # if act_name not in func_set:
        is_class_method = next((flag for name, flag in func_set if name == act_name), False)
        if act_name not in [n for n, _ in func_set] or is_class_method:
            act_name = find_by_function_name(act_name) or act_name

        aid = gen_symbol_id(act_name, ACTION)
        print(f"Processing action: {act_name} | ID: {aid}\n")
        # action_ids[aid] = act_name

        # aid = next((k for k, v in action_ids.items() if v == act_name), None)
        # if not aid:
        # if act_name not in action_ids.items():
        #     continue

        annotations = []
        node = {"id": aid}
        # set DEFAULT_ONLY for a few conditions
        if const_def_act and aid == def_act_id and def_hint:
            annotations.append("@defaultonly")
            node["annotations"] = annotations
            node["scope"] = "DEFAULT_ONLY"
        # elif def_act and act_name == "NoAction":
        elif def_act and act_name is "NoAction":
            annotations.append("@defaultonly")
            node["annotations"] = annotations
            node["scope"] = "DEFAULT_ONLY"
        elif hints.get("annotations"):
            annotations.append(hints["annotations"])
            node["annotations"] = annotations
            node["scope"] = "DEFAULT_ONLY"

        action_refs.append(node)

    table_node["actionRefs"] = action_refs

    if table.const_default_action:
    # const_def_act = table.const_default_action
    # if const_def_act is not None:
    #     func, hints = const_def_act if isinstance(const_def_act, tuple) else (const_def_act, {})
    #     const_def_act = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))

    #     if const_def_act not in func_set:
    #         const_def_act = find_by_function_name(const_def_act) or const_def_act

    #     aid = gen_symbol_id(const_def_act, ACTION)

        print(f"Processing const_default_action: {const_def_act} | ID: {def_act_id}")

        table_node["constDefaultActionId"] = def_act_id

    # attach table counters if present

    print(f"DashTableCounters._attachments: {DashTableCounters._attachments}")
    tname = table_name.rsplit(".", 1)[-1]
    print(f"table_name: {table_name}")
    if tname in DashTableCounters._attachments:
        ctr_name = DashTableCounters._attachments[tname]
        ctr = DashTableCounters._counters.get(ctr_name)
        ctr_name = f"{table_name.rsplit(".", 1)[0]}.{ctr_name}"
        cid = gen_symbol_id(ctr_name, DIRECT_COUNTER) if ctr else None
        print(f"Attaching counter '{cid} : {ctr_name}' to table '{table_name}'")
        if ctr:
            table_node["directResourceIds"] = [cid]

    # size handling (prefer structured annotation size if present)
    size = (str_annos or {}).get("size") if str_annos else None
    table_node["size"] = size if size is not None else "1024"

    return table_node

def make_action_node(act_name: str, annotations: dict, aid: int, flag: bool):
    """Create action node from action name and its annotations mapping."""
    global act_alias_names

    action_node = OrderedDict()

    # Resolve action name
    # if flag:
    #     act_name = find_by_function_name(action_entry) or action_entry
    # else:
    #     act_name = action_entry

    # Generate alias name and ensure uniqueness
    alias_name = act_name.rsplit(".", 1)[-1]
    if alias_name in act_alias_names:
        parts = act_name.split(".")
        if len(parts) >= 2:
            alias_name = ".".join(parts[-2:])
        i = 3
        while alias_name in act_alias_names and i <= len(parts):
            alias_name = ".".join(parts[-i:])
            i += 1
    act_alias_names.append(alias_name)

    # Build preamble node
    # aid = gen_symbol_id(act_name, ACTION)
    preamble_node = OrderedDict(id=aid, name=act_name, alias=alias_name)
    preamble_annotations = []

    if act_name == "NoAction":
        preamble_annotations.append('@noWarn("unused")')
        preamble_node["annotations"] = preamble_annotations
        action_node["preamble"] = preamble_node
        return action_node

    action_node["preamble"] = preamble_node

    # Build parameters node from annotations dict
    params = []
    for param_id, (k, anno) in enumerate((annotations or {}).items(), start=1):
        param_node = OrderedDict(id=param_id, name=k)
        bitwidth, str_annos = _extract_annotation_info(k, anno)
        if bitwidth is not None:
            param_node["bitwidth"] = bitwidth
        if str_annos:
            param_node["structuredAnnotations"] = _make_str_annos_node(str_annos, 1)
        params.append(param_node)

    if params:
        action_node["params"] = params
    return action_node

def make_counter_node(counter: Counter):
    """Create a general counter node."""
    cfg = counter.config
    node = OrderedDict()
    cid = gen_symbol_id(cfg.ctr_name, COUNTER)
    node["preamble"] = OrderedDict(id=cid, name=cfg.ctr_name, alias=cfg.ctr_name)

    str_annos = {}
    if getattr(cfg, "name", None):
        str_annos["name"] = cfg.name
    if getattr(cfg, "attr_type", None):
        str_annos["attr_type"] = cfg.attr_type
    if getattr(cfg, "action_names", None):
        str_annos["action_names"] = cfg.action_names
    if getattr(cfg, "no_suffix", None):
        str_annos["no_suffix"] = "true"
    if str_annos:
        node["preamble"]["structuredAnnotations"] = _make_str_annos_node(str_annos, 2)

    node["spec"] = OrderedDict(unit=cfg.counter_type.value)
    node["size"] = str(cfg.size)
    return node

def make_direct_counter_node(counter: DirectCounter, table_name: str, table_id: Optional[int] = None):
    node = OrderedDict()

    table_name = f"{table_name.rsplit(".", 1)[0]}.{counter.name}"
    d_cid = gen_symbol_id(table_name, DIRECT_COUNTER)
    node["preamble"] = OrderedDict(id=d_cid, name=table_name, alias=counter.name)
    node["spec"] = OrderedDict(unit=counter.counter_type.value)
    if table_id is not None:
        node["directTableId"] = table_id
    return node

def make_pyinfo(ignore_tables):
    """Assemble top-level pyinfo structure."""
    pyinfo = OrderedDict(pkgInfo={"arch": "python-model"})

    global func_chain, func_set, table_chain
    func_set = build_call_graph(project_dir)
    func_chain = generate_callgraph(project_dir)
    table_chain = generate_tablegraph(project_dir)

    print(f" func_set has {(func_set)} entries")

    # tables
    tables_node = []
    for tname, table in table_objs.items():
        if isinstance(table, Table) and table not in ignore_tables:
            table_name = find_by_table_name(tname) or tname
            tid = gen_symbol_id(table_name, TABLE)
            tables_node.append(make_table_node(table, table_name, tid))
            table_ids[tid] = table_name
            # print(f"Processed table: {table_name} with ID: {tid}")
        else:
            print(f"Warning: No Table object found for {tname}")
    pyinfo["tables"] = tables_node

    # actions
    actions_node = []
    aid = 0
    for func, tag in func_set:
        print(f"\nProcessing func from func_set: {func} | is_class_method: {tag}")
        if tag is True:
            print(f"Skipping class method action: {func}")
            func = find_by_function_name(func) or func

        aid = gen_symbol_id(func, ACTION)
        action_ids[aid] = func
        actions_node.append(make_action_node(func, {}, aid, False))

    for act_name, func in action_objs.items():
        # print(f"Processing func from action_objs: {act_name} {func}\n")
        # if act_name not in func_set:
        is_class_method = next((flag for name, flag in func_set if name == act_name), False)
        if act_name not in [n for n, _ in func_set] or is_class_method:
            newfunc, hints = func if isinstance(func, tuple) else (func, {})
            annotations = get_annotations(newfunc) or {}
            act_name = find_by_function_name(act_name) or act_name
            aid = gen_symbol_id(act_name, ACTION)
            actions_node.append(make_action_node(act_name, annotations, aid, True))

    pyinfo["actions"] = actions_node

    # counters
    pyinfo["counters"] = [make_counter_node(c) for c in DashCounters._counters.values()]

    # direct counters with attached table mapping if any
    direct_counters = []
    for ctr_name, counter in DashTableCounters._counters.items():
        # attached_table = next((t for t, c in DashTableCounters._attachments.items() if c == ctr_name), None)
        # table_id = next((tid for tid, tname in table_ids.items() if tname == attached_table), None) if attached_table else None

        attached_table = next((t for t, c in DashTableCounters._attachments.items() if c == ctr_name), None)
        print("Attached table found:", attached_table)


        attached_table = find_by_table_name(attached_table) or attached_table
        print("Attached table found:", attached_table)

        table_id = gen_symbol_id(attached_table, TABLE)

        # if attached_table:
        #     print("Current table_ids:", table_ids.items())

        # table_id = next((tid for tid, tname in table_ids.items() if tname == attached_table), None) if attached_table else None
        print("Table ID found:", table_id, "\n")


        direct_counters.append(make_direct_counter_node(counter, attached_table, table_id))
    pyinfo["directCounters"] = direct_counters

    # enums
    serializableEnums = OrderedDict()
    for e in get_dash_enum_list():
        serializableEnums[e.__name__] = make_enum_node(e)
    pyinfo["typeInfo"] = OrderedDict(serializableEnums=serializableEnums)

    # print(f" func_set has {(func_set)} entries")
    # print(f" table_ids has {(table_ids)} entries")
    return pyinfo

if __name__ == "__main__":
    output_dir = "dash_pipeline.py_model"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    ignore_tables = set()

    # Generate and serialize
    pyinfo = make_pyinfo(ignore_tables=[])

    # Dump to Protobuf text-format string
    textproto_output = dict_to_textproto(pyinfo)
    with open(os.path.join(output_dir, "dash_pipeline_p4rt.txt"), "w") as f:
        f.write(textproto_output + "\n")

    # Dump to Protobuf json-format string
    with open(os.path.join(output_dir, "dash_pipeline_p4rt.json"), "w") as f:
        json.dump(pyinfo, f, indent=2, sort_keys=False, cls=SafeEncoder)

    # Generate IR and save as JSON
    ir = make_ir()
    with open(os.path.join(output_dir, "dash_pipeline_ir.json"), "w") as f:
        json.dump(ir, f, indent=2, sort_keys=False)
