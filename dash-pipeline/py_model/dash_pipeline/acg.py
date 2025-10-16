#!/usr/bin/env python3
"""
Multi-file Table() chain extractor.
Start from classes in dash_pipeline.py, follow Class.method chains like in MultiFileCallGraph,
but instead of methods, stop at Table() objects defined inside classes.
Outputs dotted chains ending at Table object names.
"""

import ast
import os
from collections import defaultdict
from typing import List


class MultiFileTableGraph:
    def __init__(self, directory: str, entry_file: str = "dash_pipeline.py"):
        self.directory = os.path.abspath(directory)
        self.entry_file = os.path.join(self.directory, entry_file)
        self.class_defs = defaultdict(dict)   # {class_name: {method_name: ast.FunctionDef}}
        self.tables = defaultdict(set)        # {class_name: {table_var_names}}
        self._collect_defs_and_tables()

    # ---------------------------
    # Parse files
    # ---------------------------
    def _parse_files(self):
        for root, _, files in os.walk(self.directory):
            for fname in files:
                if fname.endswith(".py"):
                    path = os.path.join(root, fname)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            yield path, ast.parse(f.read(), filename=path)
                    except SyntaxError as e:
                        print(f"⚠️ Skipping {path} due to SyntaxError: {e}")

    # ---------------------------
    # Collect defs + Table() objects
    # ---------------------------
    def _collect_defs_and_tables(self):
        for path, tree in self._parse_files():
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = {fn.name: fn for fn in node.body if isinstance(fn, ast.FunctionDef)}
                    self.class_defs[node.name].update(methods)

                    # collect Table() assignments inside class
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                            call = stmt.value
                            if isinstance(call.func, ast.Name) and call.func.id == "Table":
                                for target in stmt.targets:
                                    if isinstance(target, ast.Name):
                                        self.tables[node.name].add(target.id)

    # ---------------------------
    # Follow class callgraph, stop at tables
    # ---------------------------
    def _get_full_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_full_name(node.value)
            return (parent + "." + node.attr) if parent else node.attr
        if isinstance(node, ast.Call):
            return self._get_full_name(node.func)
        return None

    def _extract_called_class(self, dotted_target):
        if not dotted_target:
            return None
        parts = dotted_target.split(".")
        for i in reversed(range(len(parts))):
            if parts[i] in self.class_defs:
                return parts[i]
        return None

    def _called_classes(self, func_node):
        called_classes = set()
        if func_node is None:
            return called_classes
        for stmt in ast.walk(func_node):
            if isinstance(stmt, ast.Call):
                target = self._get_full_name(stmt.func)
                callee_class = self._extract_called_class(target)
                if callee_class:
                    called_classes.add(callee_class)
        return called_classes

    def build_table_chains(self, cls_name, prefix="", visited=None):
        visited = set(visited or [])
        if cls_name in visited:
            return []
        visited.add(cls_name)

        chains = []
        methods = self.class_defs.get(cls_name, {})

        for mname, mnode in methods.items():
            for callee in sorted(self._called_classes(mnode)):
                subprefix = f"{prefix}.{cls_name}" if prefix else cls_name
                chains.extend(self.build_table_chains(callee, subprefix, visited.copy()))

        # at this class, append all tables
        if cls_name in self.tables:
            subprefix = f"{prefix}.{cls_name}" if prefix else cls_name
            for tname in sorted(self.tables[cls_name]):
                chains.append(f"{subprefix}.{tname}")

        return chains

    # ---------------------------
    # Entry point
    # ---------------------------
    def resolve_from_entry(self) -> List[str]:
        if not os.path.exists(self.entry_file):
            raise RuntimeError(f"Entry file not found: {self.entry_file!r}")

        with open(self.entry_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=self.entry_file)

        class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        if not class_nodes:
            print(f"⚠️ No classes found in entry file: {self.entry_file}")
            return []

        all_chains = []
        for cls_node in class_nodes:
            root = cls_node.name
            all_chains.extend(self.build_table_chains(root))

        # Filter only dash_ingress.* chains
        all_chains = [c for c in all_chains if c.startswith("dash_ingress.")]

        return sorted(set(all_chains))


def generate_tablegraph(project_dir: str, entry_file: str = "dash_pipeline.py") -> List[str]:
    tg = MultiFileTableGraph(project_dir, entry_file=entry_file)
    return tg.resolve_from_entry()


if __name__ == "__main__":
    project_dir = "./pmv2"
    chains = generate_tablegraph(project_dir, entry_file="dash_pipeline.py")

    print("Table object call chains:")
    for i, c in enumerate(chains, 1):
        print(i, " : ", c)
