#!/usr/bin/env python3
"""
Build a cross-file call graph using Python AST.

Enhanced:
- Prints calls found per file with file headers.
- Shows total number of unique calls at the end.
"""

import os, ast, json, builtins

def get_python_files(root_dir):
    """Return all .py files under root_dir containing 'pmv2'."""
    return [
        os.path.join(r, f)
        for r, _, files in os.walk(root_dir)
        for f in files if f.endswith(".py") and "pmv2" in r
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

def build_call_graph(root_dir):
    """Return unique list of function calls inside 'apply' functions."""
    all_calls = set()
    for pyfile in get_python_files(root_dir):
        try:
            source = open(pyfile, "r", encoding="utf-8").read()
            tree = ast.parse(source, filename=pyfile)
            tracker = ImportTracker(); tracker.visit(tree)
            visitor = CallGraphVisitor(tracker.imports); visitor.visit(tree)

            if visitor.calls:
                print(f"\n📂 File: {pyfile}")
                print("   ├─ Calls found:")
                for name, is_class_method in sorted(visitor.calls):
                    tag = " (class method)" if is_class_method else ""
                    print(f"   │   • {name}{tag}")
                print(f"   └─ Total: {len(visitor.calls)} calls")
            # else:
            #     print(f"\n📂 File: {pyfile} — no calls found.")

            all_calls.update(visitor.calls)
        except Exception as e:
            print(f"⚠️ Failed to parse {pyfile}: {e}")
    print(f"\n✅ Total unique calls across all files: {len(all_calls)}\n")
    return sorted(all_calls)

def find_string_references(root_dir, target, extensions=(".py",)):
    """Recursively search for all references of a string in the codebase."""
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
                    print(f"⚠️ Could not read {fpath}: {e}")
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate AST call graph or search for string references.")
    parser.add_argument("project_dir", help="Root directory of the DASH Python Model")
    parser.add_argument("-o","--output", default="call_graph.json", help="Output JSON file for call graph")
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
        graph = build_call_graph(args.project_dir)
        print("\n📜 Combined Call Graph:")
        print(json.dumps(graph, indent=4))
        with open(args.output, "w") as f: json.dump(graph, f, indent=4)
        print(f"\n💾 Call graph written to {args.output}")
