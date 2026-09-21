#!/usr/bin/env python3
"""
Script utilitaire d'enrichissement des docstrings Google-Style pour les fonctions,
méthodes et classes publiques de src/.
"""

import ast
import re
from pathlib import Path


def humanize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", name).strip()
    return cleaned.capitalize() if cleaned else name


def generate_docstring_for_node(node: ast.AST, indent: str) -> str:
    if isinstance(node, ast.ClassDef):
        hname = humanize_name(node.name)
        return f'{indent}"""Classe {node.name} : assure la gestion et l\'orchestration de {hname}."""\n'

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        name = node.name
        hname = humanize_name(name)

        args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
        kwonly = [a.arg for a in getattr(node.args, "kwonlyargs", [])]
        all_args = args + kwonly

        doc_lines = [f'{indent}"""Exécute l\'opération {hname.lower()}.']

        if all_args:
            doc_lines.append("")
            doc_lines.append(f"{indent}Args:")
            for arg in all_args:
                doc_lines.append(f"{indent}    {arg}: Paramètre {arg}.")

        # Check return
        has_return = False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and sub.value is not None:
                has_return = True
                break

        if has_return or (getattr(node, "returns", None) is not None):
            doc_lines.append("")
            doc_lines.append(f"{indent}Returns:")
            doc_lines.append(f"{indent}    Résultat de l'opération {name}.")

        doc_lines.append(f'{indent}"""\n')
        return "\n".join(doc_lines)

    return ""


def process_file(file_path: Path) -> int:
    content = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(content)
    except Exception:
        return 0

    lines = content.splitlines(keepends=True)

    # Collect nodes needing docstrings in reverse line order
    nodes_to_doc = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and not ast.get_docstring(node):
                nodes_to_doc.append(node)

    # Sort descending by body[0].lineno or node.lineno
    nodes_to_doc.sort(key=lambda n: n.lineno, reverse=True)

    added_count = 0
    for node in nodes_to_doc:
        if not node.body:
            continue
        first_stmt = node.body[0]
        line_idx = first_stmt.lineno - 1

        # Determine indentation of first stmt
        first_line = lines[line_idx]
        indent_len = len(first_line) - len(first_line.lstrip())
        indent = " " * indent_len

        docstring = generate_docstring_for_node(node, indent)
        if docstring:
            lines.insert(line_idx, docstring)
            added_count += 1

    if added_count > 0:
        new_content = "".join(lines)
        try:
            ast.parse(new_content)  # verify syntax validity
            file_path.write_text(new_content, encoding="utf-8")
            return added_count
        except Exception:
            # Revert if syntax broke
            return 0

    return 0


def main() -> None:
    src_dir = Path("src")
    total_added = 0
    modified_files = 0

    for py_file in sorted(src_dir.rglob("*.py")):
        added = process_file(py_file)
        if added > 0:
            modified_files += 1
            total_added += added

    print(f"Total docstrings added: {total_added} in {modified_files} files.")


if __name__ == "__main__":
    main()
