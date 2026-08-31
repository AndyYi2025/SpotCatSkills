from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

from spotcat_gates.result import GateResult


def _load_ignore_patterns(project_root: Path, ignore_file: str) -> list[str]:
    """.codebudgetignore 是可选文件（不存在 = 无额外忽略项，语义同 .gitignore 缺失时的默认行为）。"""
    ignore_path = project_root / ignore_file
    if not ignore_path.is_file():
        return []
    patterns = []
    for line in ignore_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _is_ignored(relpath: PurePosixPath, patterns: list[str]) -> bool:
    # 简化版 gitignore 语义（非完整实现）：逐行 glob，对完整相对路径和文件名分别匹配，
    # 覆盖"忽略某个具体文件"（如 legacy/big_file.py）和"忽略某类文件"（如 *_pb2.py）两种常见写法。
    rel_str = relpath.as_posix()
    return any(
        fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(relpath.name, pattern)
        for pattern in patterns
    )


def check_code_budget(config: dict, project_root: Path, files: list[Path]) -> GateResult:
    project_root = Path(project_root)
    max_loc = config["code_budget"]["max_file_loc"]
    ignore_file = config["code_budget"]["ignore_file"]
    patterns = _load_ignore_patterns(project_root, ignore_file)

    violations = []
    scanned = 0
    for f in files:
        f = Path(f)
        relpath = PurePosixPath(f.resolve().relative_to(project_root).as_posix())
        if _is_ignored(relpath, patterns):
            continue
        try:
            loc = len(f.read_text(encoding="utf-8", errors="strict").splitlines())
        except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
            return GateResult(
                gate="code-budget", status="ERROR", evidence_tier="A",
                details={"reason": f"could not read {f}: {e}"},
            )
        scanned += 1
        if loc > max_loc:
            violations.append({"file": str(relpath), "loc": loc, "max_file_loc": max_loc})

    if violations:
        return GateResult(
            gate="code-budget", status="FAIL", evidence_tier="A",
            details={"violations": violations, "scanned_files": scanned},
        )
    return GateResult(
        gate="code-budget", status="PASS", evidence_tier="A",
        details={"scanned_files": scanned, "max_file_loc": max_loc},
    )
