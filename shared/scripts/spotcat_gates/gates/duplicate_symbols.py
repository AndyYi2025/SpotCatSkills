from __future__ import annotations

import ast
from pathlib import Path

from spotcat_gates.result import GateResult


def _is_excluded_from_dup_check(relpath: Path) -> bool:
    # 测试文件里同名函数（如每个 test_*.py 都有自己的 test_basic）是正常现象，不是重复实现的信号。
    return relpath.name.startswith("test_") or "tests" in relpath.parts


def _top_level_defs(path: Path) -> list[str] | None:
    """返回顶层 def/class 名字列表；返回 None 表示文件解析失败（语法错误/编码问题）——调用方必须把
    这类文件单独列出而不是静默丢弃，否则"没查出重复"和"这个文件根本没被检查过"就分不清了。"""
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
        tree = ast.parse(text, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None
    return [
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


def check_duplicate_symbols(project_root: Path, files: list[Path]) -> GateResult:
    """检测同一个顶层函数/类名是否出现在多个文件里——只是"重名"的字面证据，不构成"一定是重复实现"的
    结论（比如多个模块各自定义同名的 Config/Result 类是常见的合理写法）。是否真的是 AI 没查现有代码就
    重写，仍需人工/LLM 判读，跟 lookahead-replay 一样标 evidence_tier B，不是 credentials 那种可以直接
    veto 的硬证据。"""
    project_root = Path(project_root)
    name_to_files: dict[str, set[str]] = {}
    unparseable: list[str] = []
    scanned = 0

    for f in files:
        f = Path(f)
        relpath = f.resolve().relative_to(project_root)
        if _is_excluded_from_dup_check(relpath):
            continue
        names = _top_level_defs(f)
        if names is None:
            unparseable.append(relpath.as_posix())
            continue
        scanned += 1
        for name in set(names):
            name_to_files.setdefault(name, set()).add(relpath.as_posix())

    duplicates = {name: sorted(locs) for name, locs in name_to_files.items() if len(locs) > 1}

    details = {"scanned_files": scanned}
    if unparseable:
        details["unparseable_files"] = sorted(unparseable)

    if duplicates:
        return GateResult(
            gate="duplicate-symbols", status="FAIL", evidence_tier="B",
            details={**details, "duplicates": duplicates},
        )
    return GateResult(gate="duplicate-symbols", status="PASS", evidence_tier="B", details=details)
