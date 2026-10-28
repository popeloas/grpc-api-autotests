"""Проверка, что у каждого теста есть метка smoke или regress.

Запуск: python tools/check_markers.py tests. Код возврата 1 и список тестов без метки."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REQUIRED_ANY = {"smoke", "regress"}


def _marker_names(nodes) -> set[str]:
    names = set()
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Attribute) \
                    and getattr(sub.value, "attr", "") == "mark":
                names.add(sub.attr)
    return names


def _module_marks(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "pytestmark" for t in node.targets):
            return _marker_names([node.value])
    return set()


def check_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_marks = _module_marks(tree)
    problems = []

    def check_func(func, inherited: set[str], owner: str = ""):
        if not func.name.startswith("test_"):
            return
        marks = inherited | _marker_names(func.decorator_list)
        if not marks & REQUIRED_ANY:
            problems.append(f"{path}:{func.lineno} {owner}{func.name} — нет метки smoke/regress")

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            check_func(node, module_marks)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_marks = module_marks | _marker_names(node.decorator_list)
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    check_func(item, class_marks, f"{node.name}.")
    return problems


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "tests")
    problems = [p for f in sorted(root.rglob("test_*.py")) for p in check_file(f)]
    for p in problems:
        print(p)
    if problems:
        print(f"\nНарушений: {len(problems)}")
        return 1
    print("OK: у всех тестов есть smoke/regress")
    return 0


if __name__ == "__main__":
    sys.exit(main())
