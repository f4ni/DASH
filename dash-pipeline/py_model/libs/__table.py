from inspect import *

from py_model.libs.__vars import *
from py_model.libs.__id_map import *

class Entry:
    class Ternary:
        def __init__(self, value: int = 0, mask: int = 0):
            self.value = value
            self.mask = mask

        def __eq__(self, other):
            return (
                isinstance(other, type(self)) and
                self.value == other.value and
                self.mask == other.mask
            )

    class LPM:
        def __init__(self, value: int = 0, prefix_len: int = 0):
            self.value = value
            self.prefix_len = prefix_len
        
        def __eq__(self, other):
            return (
                isinstance(other, type(self)) and
                self.value == other.value and
                self.prefix_len == other.prefix_len
            )

    class Range:
        def __init__(self, low: int = 0, high: int = 0):
            self.low = low
            self.high = high

        def __eq__(self, other):
            return (
                isinstance(other, type(self)) and
                self.low == other.low and
                self.high == other.high
            )

    def __init__(self,
                    values: list = None,
                    action: Callable = None,
                    params: list[int] = None,
                    priority: int = 0):
        self.values = values or []
        self.action = action
        self.params = params or []
        self.priority = priority


def EXACT(entry_value: int, match_value: int, width: int):
    print(f"EXACT entry_value: {hex(entry_value)} | match_value: {hex(match_value)}\n")
    return entry_value == match_value

def TERNARY(entry_value: Entry.Ternary, match_value: int, width: int):
    value = entry_value.value
    mask = entry_value.mask
    print(f"TERNARY match match_value: {hex(match_value)} | value: {hex(value)} | mask: {hex(mask)}\n")
    return (value & mask) == (match_value & mask)

def LIST(entry_value: list[Entry.Ternary], match_value: int, width: int):
    for ev in entry_value:
        print(f"TERNARY LIST match ev: {(ev)} | match_value: {hex(match_value)}")
        if TERNARY(ev, match_value, width):
            return True
    return False

def RANGE(entry_value: Entry.Range, match_value: int, width: int):
    low = entry_value.low
    high = entry_value.high
    print(f"RANGE match match_value: {match_value} | low: {low} | high: {high}\n")
    return match_value >= low and match_value <= high

def RANGE_LIST(entry_value: list[Entry.Range], match_value, width):
    for ev in entry_value:
        print(f"RANGE LIST match ev: {ev} | match_value: {match_value}\n")
        if RANGE(ev, match_value, width):
            return True
    return False

def LPM(entry_value: Entry.LPM, match_value: int, width: int):
    value = entry_value.value
    prefix_len = entry_value.prefix_len
    mask = ((1 << prefix_len) - 1) << (width - prefix_len)
    print(f"LPM match match_value: {hex(match_value)} | value: {hex(value)} | mask: {hex(mask)} | prefix_len: {hex(prefix_len)}\n")
    return (value & mask) == (match_value & mask)

def _winning_criteria_PRIORITY(a: Entry, b: Entry, key):
    return a.priority < b.priority

def _winning_criteria_PREFIX_LEN(a: Entry, b: Entry, key):
    idx = 0
    for k in key:
        if key[k] == LPM:
            break
        idx = idx + 1
    return a.values[idx].prefix_len > b.values[idx].prefix_len

class SaiTable:
    def __init__(self, name=None, api=None, api_type=None, order=None,
                 stage=None, isobject=None, ignored=None, match_type=None,
                 single_match_priority=None, enable_bulk_get_api=None,
                 enable_bulk_get_server=None):
        self.name = name
        self.api = api
        self.api_type = api_type
        self.order = order
        self.stage = stage
        self.isobject = isobject
        self.ignored = ignored
        self.match_type = match_type
        self.single_match_priority = single_match_priority
        self.enable_bulk_get_api = enable_bulk_get_api
        self.enable_bulk_get_server = enable_bulk_get_server

class SaiVal:
    def __init__(self, name=None, type=None, default_value=None, isresourcetype=None,
                 is_object_key=None, objects=None, isreadonly=None, iscreateonly=None,
                 match_type=None, ismandatory=None, skipattr=None):
        self.name = name
        self.type = type
        self.match_type = match_type
        self.is_object_key = is_object_key
        self.default_value = default_value
        self.isresourcetype = isresourcetype
        self.objects = objects
        self.isreadonly = isreadonly
        self.iscreateonly = iscreateonly
        self.ismandatory = ismandatory
        self.skipattr = skipattr

class Table:
    def __init__(self, key, actions, default_action=NoAction,
                 const_default_action=None, default_params=None,
                 tname=None, sai_table: SaiTable = None):

        if not tname:
            raise ValueError("Each table must have a unique 'tname'")

        self.entries = []
        table_objs[tname] = self
        # table_ids[self.id] = tname
        self.const_default_action = None
        self.const_default_action_id = None
        self.default_action = None
        self.default_action_id = None

        # store table-level hints as SaiTable
        self.sai_table = sai_table or SaiTable(name=tname)

        # convert key definitions
        self.key = {}
        self.sai_val = {}
        for k, v in key.items():
            if isinstance(v, tuple):
                match_type, meta = v
                self.key[k] = match_type
                self.sai_val[k] = SaiVal(**meta)
            else:
                self.key[k] = v

        self.default_params = default_params or []

        # register actions
        has_noAction = False
        self.actions = []
        for act in (actions or []):
            func, hints = act if isinstance(act, tuple) else (act, {})
            self._register_action(func, hints)
            self.actions.append((func, hints))
            if hints.get("annotations") == "@defaultonly":
                self.default_action = default_action
            if func is NoAction:
                self.default_action = default_action
                has_noAction = True

        # handle default vs const default only if NoAction is not present
        if const_default_action is not None:
            self._register_action(const_default_action)
            self.const_default_action = const_default_action
            self.default_action = None
            self.default_action_id = None
        else:
            # check only the function part, not the (func, hints) tuple
            if not has_noAction and not any(func is default_action for func, _ in self.actions):
                self._register_action(default_action)
                self.actions.append((NoAction, {}))
                self.default_action = default_action
                self.const_default_action = None
                self.const_default_action_id = None


    def _register_action(self, func, hints=None):
        real_func = func.__func__ if isinstance(func, staticmethod) else func
        name = getattr(real_func, "__qualname__", getattr(real_func, "__name__", str(func)))
        if name not in action_objs:
            action_objs[name] = (func, hints or {})

    def insert(self, entry):
        self.entries.append(entry)

    def update(self, entry):
        for idx, e in enumerate(self.entries):
            if e.values == entry.values:
                self.entries[idx] = entry
                print(f"Entry modified: {entry}")
                return

    def delete(self, entry):
        for e in self.entries:
            if e.values == entry.values:
                # print("Entry found for deleting +++")
                self.entries.remove(e)
                return
        # print("Entry NOT found ---\n\n")

    def apply(self):
        entry = self.__lookup()
        res = {}
        if entry is None:
            action = self.default_action or self.const_default_action
            params = self.default_params
            print(f"Match NOT found -> action: {action}\n")
            action(*params)
            res["hit"] = False
            res["action_run"] = action
        else:
            action = entry.action
            params = entry.params
            print(f"Match FOUND -> action: {action}, params = {params}\n")
            action(*params)
            res["hit"] = True
            res["action_run"] = action
        return res

    def __match_entry(self, entry: Entry):
        idx = 0
        # print(f"entry_type = {type(entry.values)} | len_entry = {len(entry.values)}")

        for k in self.key:
            if idx < len(entry.values):
                # print(f"-> Match Key: {k}")
                _read_value_res = _read_value(k)
                match_value = _read_value_res[0]
                width = _read_value_res[1]
                match_routine = self.key[k]
                entry_value = entry.values[idx]

                if match_routine == EXACT:
                    if type(entry_value) is not int:
                        entry_value = int(entry_value, 16)
                    if type(match_value) is not int:
                        match_value = int(match_value, 16)
                    ret = EXACT(entry_value, match_value, width)

                elif match_routine == TERNARY:
                    entry_obj = Entry.Ternary()
                    entry_obj.value = entry_value.value
                    entry_obj.mask = entry_value.mask
                    ret = TERNARY(entry_obj, match_value, width)

                elif match_routine == LPM:
                    entry_obj = Entry.LPM()
                    entry_obj.value = int(entry_value.value, 16)
                    entry_obj.prefix_len = entry_value.prefix_len
                    ret = LPM(entry_obj, match_value, width)

                elif match_routine == RANGE:
                    entry_obj = Entry.Range()
                    entry_obj.low = entry_value.low
                    entry_obj.high = entry_value.high
                    ret = RANGE(entry_obj, match_value, width)

                elif match_routine == LIST:
                    entry_list = entry_value
                    ret = LIST(entry_list, match_value, width)

                elif match_routine == RANGE_LIST:
                    entry_range_list = entry_value
                    ret = RANGE_LIST(entry_range_list, match_value, width)

                if ret == False:
                    return False
                idx = idx + 1
        return True

    def __get_all_matching_entries(self):
        matching_entries = []
        # print(f"Match_Entries = {list(self.entries)}")
        for e in self.entries:
            # print(f"matching entry = {e}")
            if self.__match_entry(e):
                matching_entries.append(e)
        return matching_entries

    def __get_winning_criteria(self):
        # print(f"self.key = {self.key}")
        for k in self.key:
            if self.key[k]==LPM:
                return _winning_criteria_PREFIX_LEN
        for k in self.key:
            if self.key[k]==EXACT or self.key[k]==TERNARY or self.key[k]==LIST or self.key[k]==RANGE or self.key[k]==RANGE_LIST:
                return _winning_criteria_PRIORITY
        return None

    def __select_winning_entry(self, matching_entries):
        # print(f"matching_entries = {list(matching_entries)}")
        winning_criteria = self.__get_winning_criteria()
        curr_winner = matching_entries[0]
        for e in matching_entries[1:]:
            if winning_criteria(e, curr_winner, self.key):
                curr_winner = e
        return curr_winner

    def __lookup(self):
        matching_entries = self.__get_all_matching_entries()
        if not matching_entries:
            return None
        else:
            entry = self.__select_winning_entry(matching_entries)
            return entry

def _read_value(input):
    tokens = input.split(".")
    container = globals()[tokens[0]]
    var_name = tokens[1]
    var = getattr(container, var_name)
    for token in tokens[2:]:
        container = var
        var_name = token
        var = getattr(container, var_name)
    width = (get_annotations(type(container))[var_name].__metadata__)[0]
    return (var, width)
