#!/usr/bin/env python3
"""
Build a cross-file call chain using Python AST.

Features:
- Recursively scans .py files under 'data_plane'.
- Collects only calls inside 'apply' functions.
- Filters out unwanted names (apply, *_apply, *_t, uppercase, .apply, builtins).
- Returns a unique list of function calls (last part only).
- Can also search for raw string references across the codebase.
"""

import os, ast, json, builtins

def get_python_files(root_dir):
    """Return all .py files under root_dir containing 'data_plane'."""
    return [
        os.path.join(r, f)
        for r, _, files in os.walk(root_dir)
        for f in files if f.endswith(".py") and "data_plane" in r
    ]

class ImportTracker(ast.NodeVisitor):
    """Tracks import statements in a file."""
    def __init__(self):
        self.imports = {}
    def visit_Import(self, node):
        for a in node.names:
            self.imports[a.asname or a.name] = a.name
    def visit_ImportFrom(self, node):
        for a in node.names:
            self.imports[a.asname or a.name] = f"{node.module}.{a.name}" if node.module else a.name

class CallGraphVisitor(ast.NodeVisitor):
    """Collects calls inside 'apply' functions."""
    def __init__(self, imports):
        self.imports, self.calls, self.current = imports, set(), None
        self.skip = set(dir(builtins)) | {
            "get","keys","values","items","update","append","extend","insert",
            "pop","remove","clear","copy"
        }

    def visit_FunctionDef(self, node):
        if node.name == "apply":
            self.current = node.name
            self.generic_visit(node)
            self.current = None

    def visit_Call(self, node):
        if not self.current:
            return

        name = None
        is_class_method = False

        if isinstance(node.func, ast.Name):
            name = self.imports.get(node.func.id, node.func.id)

        elif isinstance(node.func, ast.Attribute):
            # Detect self/cls method calls
            if isinstance(node.func.value, ast.Name) and node.func.value.id in ("self", "cls"):
                is_class_method = True
            name = node.func.attr

        if name:
            name = name.split(".")[-1]
            if not (
                name == "apply" or name == "py_log" or 
                name.endswith("_apply") or name.endswith("_t") or 
                name.isupper() or name in self.skip
            ):
                # Store as tuple (name, is_class_method)
                self.calls.add((name, is_class_method))

        self.generic_visit(node)

def generate_call_chain(root_dir):
    """Return unique list of function calls inside 'apply' functions."""
    all_calls = set()
    for pyfile in get_python_files(root_dir):
        try:
            source = open(pyfile, "r", encoding="utf-8").read()
            tree = ast.parse(source, filename=pyfile)
            tracker = ImportTracker(); tracker.visit(tree)
            visitor = CallGraphVisitor(tracker.imports); visitor.visit(tree)
            all_calls.update(visitor.calls)
        except Exception as e:
            print(f"Failed to parse {pyfile}: {e}")
    return sorted(all_calls)

def find_string_references(root_dir, target, extensions=(".py",)):
    """
    Recursively search for all references of a string in the codebase.

    Args:
        root_dir (str): Root directory of your project.
        target (str): The string to search for.
        extensions (tuple): File extensions to include (default: only Python files).

    Returns:
        dict: {filepath: [list of (line_number, line_text)]}
    """
    results = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(extensions):
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, start=1):
                            if target in line:
                                results.setdefault(fpath, []).append((lineno, line.strip()))
                except Exception as e:
                    print(f"Could not read {fpath}: {e}")
    return results

if __name__ == "__main__":
    """
    To run this script:
        Generate call chain:
            python3 call_graph.py . -o project_call_graph.json
        Search for string references:
            python3 call_graph.py . --find drop_action
    """
    import argparse
    parser = argparse.ArgumentParser(description="Generate AST call chain or search for string references.")
    parser.add_argument("project_dir", help="Root directory of the DASH Python Model")
    parser.add_argument("-o","--output", default="py_model/scripts/call_graph.json", help="Output JSON file for call chain")
    parser.add_argument("--find", help="String to search for in the codebase")
    args = parser.parse_args()

    if args.find:
        refs = find_string_references(args.project_dir, args.find)
        if refs:
            for file, matches in refs.items():
                print(f"\nIn {file}:")
                for lineno, text in matches:
                    print(f"  Line {lineno}: {text}")
        else:
            print(f"No references of '{args.find}' found.")
    else:
        graph = generate_call_chain(args.project_dir)
        print("\nCombined call chain:")
        print(json.dumps(graph, indent=4))
        with open(args.output, "w") as f: json.dump(graph, f, indent=4)
        print(f"\nCall graph written to {args.output}")
