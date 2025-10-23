#!/usr/bin/env python3
"""
Optimized Multi-file Counter() chain extractor.

Searches for DEFINE_*() and DEFINE_TABLE_*() calls inside classes,
extracting counter names and resolving dotted call chains.
"""

import ast
import os
from collections import defaultdict
from typing import List, Tuple


class MultiFileCounterGraph:
    def __init__(self, directory: str, entry_file: str = "dash_pipeline.py", verbose: bool = False):
        self.directory = os.path.abspath(directory)
        self.entry_file = os.path.join(self.directory, entry_file)
        self.verbose = verbose

        # Data structures
        self.class_defs = defaultdict(dict)       # {class_name: {method_name: ast.FunctionDef}}
        self.counters = defaultdict(set)          # {class_name: {counter_names}}
        self.directcounters = defaultdict(set)    # {class_name: {table_counter_names}}
        self.called_class_cache = {}              # Cache per function node
        self.class_call_cache = {}                # Cache per class (aggregated)

        # Parse and collect
        self.parsed_files = list(self._parse_files())
        self._collect_defs_and_counters()

    # ---------------------------
    # Parse all .py files (skip irrelevant dirs)
    # ---------------------------
    def _parse_files(self):
        skip_dirs = {"__pycache__", "venv", "site-packages", "tests"}
        for root, _, files in os.walk(self.directory):
            if any(skip in root for skip in skip_dirs):
                continue
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        yield path, ast.parse(f.read(), filename=path)
                except SyntaxError as e:
                    print(f"⚠️ Skipping {path}: {e}")

    # ---------------------------
    # Collect class definitions and DEFINE_*() counters
    # ---------------------------
    def _collect_defs_and_counters(self):
        for path, tree in self.parsed_files:
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue

                # Store methods
                self.class_defs[node.name].update(
                    {fn.name: fn for fn in node.body if isinstance(fn, ast.FunctionDef)}
                )

                # Collect DEFINE_* and DEFINE_TABLE_* calls
                for stmt in ast.walk(node):
                    if not isinstance(stmt, ast.Call):
                        continue

                    func = stmt.func
                    func_name = (
                        func.id if isinstance(func, ast.Name)
                        else getattr(func, "attr", None)
                    )
                    if not func_name or not func_name.startswith("DEFINE_"):
                        continue

                    if stmt.args and isinstance(stmt.args[0], ast.Constant) and isinstance(stmt.args[0].value, str):
                        cname = stmt.args[0].value
                        if func_name.startswith("DEFINE_TABLE_"):
                            self.directcounters[node.name].add(cname)
                            if self.verbose:
                                print(f"[TABLE] {node.name}: {cname}")
                        else:
                            self.counters[node.name].add(cname)
                            if self.verbose:
                                print(f"[COUNTER] {node.name}: {cname}")

    # ---------------------------
    # Extract called class from a Call node
    # ---------------------------
    def _extract_called_class(self, func_node):
        """Return the class name if call target refers to a known class."""
        if isinstance(func_node, ast.Attribute):
            target = func_node
            while isinstance(target, ast.Attribute):
                if target.attr in self.class_defs:
                    return target.attr
                target = target.value
            if isinstance(target, ast.Name) and target.id in self.class_defs:
                return target.id
        elif isinstance(func_node, ast.Name) and func_node.id in self.class_defs:
            return func_node.id
        return None

    def _called_classes(self, func_node):
        """Return set of class names called inside a function."""
        if func_node is None:
            return set()
        if func_node in self.called_class_cache:
            return self.called_class_cache[func_node]

        called_classes = {
            callee for stmt in ast.walk(func_node)
            if isinstance(stmt, ast.Call)
            and (callee := self._extract_called_class(stmt.func))
        }
        self.called_class_cache[func_node] = called_classes
        return called_classes

    # ---------------------------
    # Recursive chain builder
    # ---------------------------
    def _build_chains(self, cls_name, counter_dict, prefix="", visited=None):
        visited = visited or set()
        if cls_name in visited:
            return []

        visited.add(cls_name)
        chains = []
        subprefix = f"{prefix}.{cls_name}" if prefix else cls_name

        methods = self.class_defs.get(cls_name, {})
        for mnode in methods.values():
            for callee in self._called_classes(mnode):
                chains.extend(self._build_chains(callee, counter_dict, subprefix, visited))

        if cls_name in counter_dict:
            chains.extend(f"{subprefix}.{c}" for c in counter_dict[cls_name])

        visited.remove(cls_name)
        return chains

    # ---------------------------
    # Entry point
    # ---------------------------
    def resolve_from_entry(self) -> Tuple[list[str], list[str]]:
        if not os.path.exists(self.entry_file):
            raise RuntimeError(f"Entry file not found: {self.entry_file!r}")

        with open(self.entry_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=self.entry_file)

        class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        if not class_nodes:
            print(f"No classes found in entry file: {self.entry_file}")
            return [], []

        all_chains, dir_chains = [], []
        for cls_node in class_nodes:
            root = cls_node.name
            all_chains += self._build_chains(root, self.counters)
            dir_chains += self._build_chains(root, self.directcounters)

        all_chains = sorted({c for c in all_chains if c.startswith("dash_ingress.")})
        dir_chains = sorted({c for c in dir_chains if c.startswith("dash_ingress.")})
        return all_chains, dir_chains


# ---------------------------
# Wrapper
# ---------------------------
def generate_counter_chain(project_dir: str, entry_file: str = "dash_pipeline.py", verbose=False) -> Tuple[list[str], list[str]]:
    cg = MultiFileCounterGraph(project_dir, entry_file=entry_file, verbose=verbose)
    return cg.resolve_from_entry()


if __name__ == "__main__":
    project_dir = "py_model/data_plane"

    chains, dir_chains = generate_counter_chain(project_dir, entry_file="dash_pipeline.py")

    print("Counter call chains:")
    for i, c in enumerate(chains, 1):
        print(i, ":", c)

    print(f"\nDirect counter call chains ({len(dir_chains)}):")
    for i, c in enumerate(dir_chains, 1):
        print(i, ":", c)
