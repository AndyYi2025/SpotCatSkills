# Quant Gate Layer (P0+P1+P2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Give SpotCat a real, executable gate-script layer (P0 资金安全硬门 + P1 回测证据完整性 + P2
`data_hash` 审计) that a quality-review agent runs and reads structured JSON from, instead of self-reporting
whether checks passed. This is the single-pilot-project deliverable; multi-project distribution (P3) and
code-hygiene cleanup (P4) are separate follow-up plans per the spec's own sequencing.

**Architecture:** A Python package `shared/scripts/spotcat_gates/` with one function per gate (`GateResult` in,
`GateResult` out: `status: PASS|FAIL|ERROR`, `evidence_tier`, `details`), orchestrated by `gate_runner.py`,
which writes its own JSON result to `.spotcat/runs/<run_id>/gate-output.json` as a side effect of running (not
dependent on an external harness capturing stdout — this is how "output captured independently, not via agent
transcription" gets implemented without assuming anything about the not-yet-decided Cron harness). Three P0
gates (position-limit, idempotency, dual kill-switch) share one helper that runs the project's `commands.test`
once and checks for named tests in the `pytest-json-report` output, rather than each gate re-running the suite.
P1's date-gap and lookahead-replay checks are gates that make `gate_runner.py` exit non-zero on failure — they
are not deferred to a separate "P2 phase".

**Tech Stack:** Python 3.11+, `pyyaml` (config parsing), `jsonschema` (schema validation), `pytest` +
`pytest-json-report` (test running/parsing) for the test suite itself and for parsing consuming-project test
output.

**Spec:** `docs/superpowers/specs/2026-08-25-quant-dev-infra-redesign-design.md` (§2 P0, §3 P1, §4 P2, §8
reusable megaview patterns, §9 acceptance criteria — this plan implements §9's P0/P1/P2 rows only).

## Global Constraints

- Every gate function returns a `GateResult` with `status` one of exactly `"PASS"`, `"FAIL"`, `"ERROR"` — never
  a bare bool. `ERROR` means the gate itself could not determine an answer (config missing, subprocess crashed,
  output unparseable); `FAIL` means the gate ran successfully and determined the checked condition is violated.
  Conflating the two is the exact bug the spec's §3 "谁测试这些脚本" section warns against.
- No gate silently defaults a missing config field — missing required config = `ERROR`, not a guessed value
  (spec §2.2 "fail-closed，不做默认值").
- `gate_runner.py` must exit non-zero if any gate's `status` is `FAIL` or `ERROR`. Never exit 0 with a failing
  gate in the JSON.
- Every gate module gets a pytest file with at least one PASS case, one FAIL case, and (where applicable) one
  ERROR case, mirroring megaview's `check-code-budget.test.sh` fixture pattern (spec §8.2).
- `.spotcat/config.yml`'s `spotcat_schema_version` must equal the version this codebase expects (`1`); mismatch
  = `ConfigError`, not a silent field-by-field fallback.

---

## Task 1: Config loader (fail-closed schema validation)

**Files:**
- Create: `shared/scripts/spotcat_gates/__init__.py`
- Create: `shared/scripts/spotcat_gates/config.py`
- Create: `shared/schemas/config.schema.json`
- Create: `shared/config.example.yml`
- Test: `shared/scripts/tests/test_config.py`
- Create: `shared/scripts/pyproject.toml`
- Create: `shared/scripts/tests/__init__.py`

**Interfaces:**
- Produces: `spotcat_gates.config.load_config(path: str | Path) -> dict` — raises `spotcat_gates.config.ConfigError`
  on any missing required field, schema mismatch, or unreadable file. Never returns a partially-filled dict.
- Produces: `spotcat_gates.config.ConfigError(Exception)`

- [ ] **Step 1: Create package skeleton and pyproject.toml**

```
mkdir -p shared/scripts/spotcat_gates shared/scripts/tests shared/schemas
```

`shared/scripts/pyproject.toml`:
```toml
[project]
name = "spotcat-gates"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0", "jsonschema>=4.20"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-json-report>=1.5"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`shared/scripts/spotcat_gates/__init__.py`:
```python
```

`shared/scripts/tests/__init__.py`:
```python
```

- [ ] **Step 2: Write the JSON schema for config.yml**

`shared/schemas/config.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SpotCat project config",
  "type": "object",
  "required": ["version", "spotcat_schema_version", "paths", "commands", "thresholds", "code_budget", "safety"],
  "additionalProperties": false,
  "properties": {
    "version": {"type": "integer"},
    "spotcat_schema_version": {"type": "integer"},
    "paths": {
      "type": "object",
      "required": ["data_root", "data_format", "expected_date_range"],
      "additionalProperties": false,
      "properties": {
        "data_root": {"type": "string", "minLength": 1},
        "data_format": {"type": "string", "minLength": 1},
        "expected_date_range": {
          "type": "object",
          "required": ["start", "end"],
          "additionalProperties": false,
          "properties": {
            "start": {"type": "string", "format": "date"},
            "end": {"type": "string"}
          }
        },
        "replay_check_dates": {
          "type": "object",
          "required": ["t", "t_plus_k"],
          "additionalProperties": false,
          "properties": {
            "t": {"type": "string", "format": "date"},
            "t_plus_k": {"type": "string", "format": "date"}
          }
        }
      }
    },
    "commands": {
      "type": "object",
      "required": ["test", "backtest"],
      "additionalProperties": false,
      "properties": {
        "test": {"type": "string", "minLength": 1},
        "backtest": {"type": "string", "minLength": 1},
        "lookahead_replay": {"type": "string", "minLength": 1}
      }
    },
    "thresholds": {
      "type": "object",
      "required": ["min_sharpe", "max_drawdown", "min_trades", "max_oos_is_gap_pct"],
      "additionalProperties": false,
      "properties": {
        "min_sharpe": {"type": "number"},
        "max_drawdown": {"type": "number"},
        "min_trades": {"type": "integer"},
        "max_oos_is_gap_pct": {"type": "number"},
        "lookahead_replay_offset_days": {"type": "integer", "default": 5}
      }
    },
    "code_budget": {
      "type": "object",
      "required": ["max_file_loc", "ignore_file"],
      "additionalProperties": false,
      "properties": {
        "max_file_loc": {"type": "integer"},
        "ignore_file": {"type": "string"}
      }
    },
    "safety": {
      "type": "object",
      "required": ["paper_only", "live_enable_flag_path", "global_kill_switch", "idempotency_key_format"],
      "additionalProperties": false,
      "properties": {
        "paper_only": {"type": "boolean"},
        "live_enable_flag_path": {"type": "string", "minLength": 1},
        "global_kill_switch": {"type": "string", "minLength": 1},
        "idempotency_key_format": {"type": "string", "minLength": 1}
      }
    }
  }
}
```

- [ ] **Step 3: Write the failing test**

`shared/scripts/tests/test_config.py`:
```python
import json
import textwrap
from pathlib import Path

import pytest

from spotcat_gates.config import ConfigError, load_config

VALID_YAML = textwrap.dedent("""\
    version: 1
    spotcat_schema_version: 1
    paths:
      data_root: /tmp/data
      data_format: parquet
      expected_date_range: { start: "2024-01-01", end: "2024-12-31" }
    commands:
      test: "pytest tests/ -v --json-report --json-report-file=.spotcat/last-test-result.json"
      backtest: "python -m backtest.run --strategy {strategy}"
    thresholds:
      min_sharpe: 1.0
      max_drawdown: 0.15
      min_trades: 30
      max_oos_is_gap_pct: 50
    code_budget:
      max_file_loc: 500
      ignore_file: .codebudgetignore
    safety:
      paper_only: true
      live_enable_flag_path: .spotcat/LIVE_ENABLED
      global_kill_switch: "~/.spotcat/GLOBAL_LIVE_ENABLE"
      idempotency_key_format: "{strategy_id}_{signal_timestamp}_{side}"
    """)


def test_load_config_valid(tmp_path):
    p = tmp_path / "config.yml"
    p.write_text(VALID_YAML)
    cfg = load_config(p)
    assert cfg["safety"]["paper_only"] is True
    assert cfg["thresholds"]["min_sharpe"] == 1.0


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")


def test_load_config_missing_required_field(tmp_path):
    bad = VALID_YAML.replace("min_sharpe: 1.0\n", "")
    p = tmp_path / "config.yml"
    p.write_text(bad)
    with pytest.raises(ConfigError, match="schema"):
        load_config(p)


def test_load_config_wrong_schema_version(tmp_path):
    bad = VALID_YAML.replace("spotcat_schema_version: 1", "spotcat_schema_version: 2")
    p = tmp_path / "config.yml"
    p.write_text(bad)
    with pytest.raises(ConfigError, match="spotcat_schema_version"):
        load_config(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `shared/scripts/`): `pip install -e ".[dev]" && pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.config'`

- [ ] **Step 5: Write minimal implementation**

`shared/scripts/spotcat_gates/config.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

SCHEMA_VERSION = 1
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "config.schema.json"


class ConfigError(Exception):
    pass


def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"config not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"config is not valid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=raw, schema=schema)
    except jsonschema.ValidationError as e:
        raise ConfigError(f"config failed schema validation: {e.message}") from e

    if raw["spotcat_schema_version"] != SCHEMA_VERSION:
        raise ConfigError(
            f"spotcat_schema_version {raw['spotcat_schema_version']} != expected {SCHEMA_VERSION}; "
            "run the config migration before continuing"
        )

    return raw
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 7: Write the example config template**

`shared/config.example.yml` — copy of `VALID_YAML` above verbatim (this is what consuming projects copy into
`.spotcat/config.yml` and edit).

- [ ] **Step 8: Commit**

```bash
git add shared/scripts/pyproject.toml shared/scripts/spotcat_gates/__init__.py \
  shared/scripts/spotcat_gates/config.py shared/schemas/config.schema.json \
  shared/config.example.yml shared/scripts/tests/__init__.py shared/scripts/tests/test_config.py
git commit -m "feat(gates): add fail-closed config loader with schema versioning"
```

---

## Task 2: Gate result protocol

**Files:**
- Create: `shared/scripts/spotcat_gates/result.py`
- Test: `shared/scripts/tests/test_result.py`

**Interfaces:**
- Consumes: nothing (pure data type, first module in the dependency graph).
- Produces: `spotcat_gates.result.GateResult(gate: str, status: str, evidence_tier: str, details: dict)` —
  `status` restricted to `{"PASS", "FAIL", "ERROR"}`, `evidence_tier` restricted to `{"A", "B", "C"}`. Method
  `.to_dict() -> dict` for JSON serialization. Every later gate module imports this.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/test_result.py`:
```python
import pytest

from spotcat_gates.result import GateResult


def test_valid_result_to_dict():
    r = GateResult(gate="credentials", status="PASS", evidence_tier="A", details={"scanned_files": 3})
    assert r.to_dict() == {
        "gate": "credentials",
        "status": "PASS",
        "evidence_tier": "A",
        "details": {"scanned_files": 3},
    }


def test_invalid_status_rejected():
    with pytest.raises(ValueError, match="status"):
        GateResult(gate="credentials", status="MAYBE", evidence_tier="A", details={})


def test_invalid_evidence_tier_rejected():
    with pytest.raises(ValueError, match="evidence_tier"):
        GateResult(gate="credentials", status="PASS", evidence_tier="Z", details={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_result.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.result'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/result.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

_VALID_STATUS = {"PASS", "FAIL", "ERROR"}
_VALID_TIER = {"A", "B", "C"}


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str
    evidence_tier: str
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in _VALID_STATUS:
            raise ValueError(f"status must be one of {_VALID_STATUS}, got {self.status!r}")
        if self.evidence_tier not in _VALID_TIER:
            raise ValueError(f"evidence_tier must be one of {_VALID_TIER}, got {self.evidence_tier!r}")

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "status": self.status,
            "evidence_tier": self.evidence_tier,
            "details": self.details,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_result.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/result.py shared/scripts/tests/test_result.py
git commit -m "feat(gates): add GateResult with PASS/FAIL/ERROR three-state status"
```

---

## Task 3: Output capture (run_id + disk write)

**Files:**
- Create: `shared/scripts/spotcat_gates/capture.py`
- Test: `shared/scripts/tests/test_capture.py`

**Interfaces:**
- Consumes: `spotcat_gates.result.GateResult` (Task 2).
- Produces: `spotcat_gates.capture.write_gate_output(project_root: Path, run_id: str, results: list[GateResult], overall_status: str) -> Path` —
  writes `.spotcat/runs/<run_id>/gate-output.json`, returns the written path. Raises `ValueError` if `run_id`
  contains path-traversal characters (`/`, `\`, `..`).
- Produces: `spotcat_gates.capture.new_run_id() -> str` — timestamp + random hex, for standalone/manual runs.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/test_capture.py`:
```python
import json

import pytest

from spotcat_gates.capture import new_run_id, write_gate_output
from spotcat_gates.result import GateResult


def test_write_gate_output_creates_file(tmp_path):
    results = [GateResult(gate="credentials", status="PASS", evidence_tier="A", details={})]
    out = write_gate_output(tmp_path, "20260826-abcd12", results, overall_status="PASS")
    assert out == tmp_path / ".spotcat" / "runs" / "20260826-abcd12" / "gate-output.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["run_id"] == "20260826-abcd12"
    assert payload["overall_status"] == "PASS"
    assert payload["gates"] == [
        {"gate": "credentials", "status": "PASS", "evidence_tier": "A", "details": {}}
    ]


def test_write_gate_output_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="run_id"):
        write_gate_output(tmp_path, "../escape", [], overall_status="PASS")


def test_new_run_id_format():
    rid = new_run_id()
    assert len(rid.split("-")) == 2
    date_part, hex_part = rid.split("-")
    assert len(date_part) == 15  # YYYYMMDD-HHMMSS minus the dash, see impl
    assert len(hex_part) == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.capture'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/capture.py`:
```python
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from spotcat_gates.result import GateResult


def new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{secrets.token_hex(4)}"


def write_gate_output(
    project_root: Path, run_id: str, results: list[GateResult], overall_status: str
) -> Path:
    if any(c in run_id for c in ("/", "\\")) or ".." in run_id:
        raise ValueError(f"run_id must not contain path separators or '..': {run_id!r}")

    run_dir = Path(project_root) / ".spotcat" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "gate-output.json"

    payload = {
        "run_id": run_id,
        "overall_status": overall_status,
        "gates": [r.to_dict() for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capture.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/capture.py shared/scripts/tests/test_capture.py
git commit -m "feat(gates): add run_id-scoped disk output capture (not agent-mediated)"
```

---

## Task 4: Test-report helper (shared by position-limit/idempotency/kill-switch gates)

**Files:**
- Create: `shared/scripts/spotcat_gates/test_report.py`
- Test: `shared/scripts/tests/test_test_report.py`

**Interfaces:**
- Consumes: `spotcat_gates.result.GateResult` (Task 2), `dict` config (Task 1 shape).
- Produces: `spotcat_gates.test_report.run_test_command(config: dict, project_root: Path) -> dict` — runs
  `config["commands"]["test"]` via subprocess in `project_root`, loads and returns the `pytest-json-report`
  JSON. Raises `TestReportError` (defined here) if the command fails to run or the report file is missing/
  unparseable — callers turn that into `GateResult(status="ERROR")`.
- Produces: `spotcat_gates.test_report.check_named_test(report: dict, test_name_suffix: str) -> tuple[bool, bool]` —
  returns `(found, passed)`. `found=False` means no test whose `nodeid` ends with `test_name_suffix` exists in
  the report.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/test_test_report.py`:
```python
import json
import textwrap

import pytest

from spotcat_gates.test_report import TestReportError, check_named_test, run_test_command

REPORT = {
    "tests": [
        {"nodeid": "tests/test_risk.py::test_position_limit_enforced", "outcome": "passed"},
        {"nodeid": "tests/test_risk.py::test_duplicate_signal_not_double_ordered", "outcome": "failed"},
    ]
}


def test_check_named_test_found_and_passed():
    found, passed = check_named_test(REPORT, "test_position_limit_enforced")
    assert (found, passed) == (True, True)


def test_check_named_test_found_and_failed():
    found, passed = check_named_test(REPORT, "test_duplicate_signal_not_double_ordered")
    assert (found, passed) == (True, False)


def test_check_named_test_not_found():
    found, passed = check_named_test(REPORT, "test_live_trading_requires_dual_kill_switch")
    assert (found, passed) == (False, False)


def test_run_test_command_success(tmp_path):
    report_path = tmp_path / ".spotcat" / "last-test-result.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(REPORT), encoding="utf-8")

    # command just needs to exit 0; report already on disk for this fixture
    config = {"commands": {"test": "python -c \"pass\""}}
    result = run_test_command(config, tmp_path, report_relpath=".spotcat/last-test-result.json")
    assert result == REPORT


def test_run_test_command_missing_report_raises(tmp_path):
    config = {"commands": {"test": "python -c \"pass\""}}
    with pytest.raises(TestReportError, match="report file not found"):
        run_test_command(config, tmp_path, report_relpath=".spotcat/last-test-result.json")


def test_run_test_command_nonzero_exit_still_reads_report(tmp_path):
    # pytest itself exits non-zero when tests fail — that's expected, not a gate ERROR.
    report_path = tmp_path / ".spotcat" / "last-test-result.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(REPORT), encoding="utf-8")
    config = {"commands": {"test": "python -c \"import sys; sys.exit(1)\""}}
    result = run_test_command(config, tmp_path, report_relpath=".spotcat/last-test-result.json")
    assert result == REPORT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.test_report'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/test_report.py`:
```python
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path


class TestReportError(Exception):
    pass


def run_test_command(
    config: dict, project_root: Path, report_relpath: str = ".spotcat/last-test-result.json"
) -> dict:
    cmd = config["commands"]["test"]
    try:
        subprocess.run(cmd, shell=True, cwd=project_root, timeout=1800)
    except (subprocess.SubprocessError, OSError) as e:
        raise TestReportError(f"test command failed to run: {e}") from e

    report_path = Path(project_root) / report_relpath
    if not report_path.is_file():
        raise TestReportError(f"report file not found: {report_path}")

    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TestReportError(f"report file is not valid JSON: {e}") from e


def check_named_test(report: dict, test_name_suffix: str) -> tuple[bool, bool]:
    for t in report.get("tests", []):
        if t.get("nodeid", "").endswith(test_name_suffix):
            return True, t.get("outcome") == "passed"
    return False, False
```

Note: `shlex` import is unused after this minimal implementation — remove it (kept out to avoid an unused-import
lint failure; `subprocess.run(cmd, shell=True, ...)` takes the raw string directly).

- [ ] **Step 4: Remove the unused import**

Edit `shared/scripts/spotcat_gates/test_report.py`, delete the line `import shlex`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_test_report.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add shared/scripts/spotcat_gates/test_report.py shared/scripts/tests/test_test_report.py
git commit -m "feat(gates): add shared pytest-json-report runner/parser for behavioral gates"
```

---

## Task 5: P0 behavioral gates — position-limit, idempotency, dual kill-switch

**Files:**
- Create: `shared/scripts/spotcat_gates/gates/__init__.py`
- Create: `shared/scripts/spotcat_gates/gates/behavioral.py`
- Test: `shared/scripts/tests/gates/test_behavioral.py`
- Create: `shared/scripts/tests/gates/__init__.py`

**Interfaces:**
- Consumes: `spotcat_gates.test_report.run_test_command`, `check_named_test`, `TestReportError` (Task 4);
  `spotcat_gates.result.GateResult` (Task 2).
- Produces: `spotcat_gates.gates.behavioral.check_position_limit(report: dict) -> GateResult`
- Produces: `spotcat_gates.gates.behavioral.check_idempotency(report: dict) -> GateResult`
- Produces: `spotcat_gates.gates.behavioral.check_kill_switch(report: dict) -> GateResult`
- Produces: `spotcat_gates.gates.behavioral.REQUIRED_TEST_NAMES` — dict mapping gate name to required test-name
  suffix, so `gate_runner.py` (Task 11) knows what's required without duplicating the literal names.

**Design decision locked in for this task** (extends the spec's position-limit pattern to kill-switch, since
the spec's §2.2 describes the dual-switch *mechanism* but not how quality-review verifies the code respects it —
same "existence is not enough" reasoning applies): the required test is
`test_live_trading_requires_dual_kill_switch`, asserting the order-entry path refuses to trade when either
switch is off and only trades when both are on.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/gates/__init__.py`:
```python
```

`shared/scripts/tests/gates/test_behavioral.py`:
```python
from spotcat_gates.gates.behavioral import check_idempotency, check_kill_switch, check_position_limit

PASSING_REPORT = {
    "tests": [
        {"nodeid": "tests/test_risk.py::test_position_limit_enforced", "outcome": "passed"},
        {"nodeid": "tests/test_risk.py::test_duplicate_signal_not_double_ordered", "outcome": "passed"},
        {"nodeid": "tests/test_risk.py::test_live_trading_requires_dual_kill_switch", "outcome": "passed"},
    ]
}

FAILING_REPORT = {
    "tests": [
        {"nodeid": "tests/test_risk.py::test_position_limit_enforced", "outcome": "failed"},
    ]
}

EMPTY_REPORT = {"tests": []}


def test_position_limit_pass():
    r = check_position_limit(PASSING_REPORT)
    assert r.status == "PASS"
    assert r.gate == "position-limit"
    assert r.evidence_tier == "A"


def test_position_limit_fail_when_test_fails():
    r = check_position_limit(FAILING_REPORT)
    assert r.status == "FAIL"
    assert "failed" in r.details["reason"]


def test_position_limit_fail_when_test_missing():
    r = check_position_limit(EMPTY_REPORT)
    assert r.status == "FAIL"
    assert "not found" in r.details["reason"]


def test_idempotency_pass():
    assert check_idempotency(PASSING_REPORT).status == "PASS"


def test_kill_switch_pass():
    assert check_kill_switch(PASSING_REPORT).status == "PASS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gates/test_behavioral.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.gates'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/gates/__init__.py`:
```python
```

`shared/scripts/spotcat_gates/gates/behavioral.py`:
```python
from __future__ import annotations

from spotcat_gates.result import GateResult
from spotcat_gates.test_report import check_named_test

REQUIRED_TEST_NAMES = {
    "position-limit": "test_position_limit_enforced",
    "idempotency": "test_duplicate_signal_not_double_ordered",
    "kill-switch": "test_live_trading_requires_dual_kill_switch",
}


def _check(gate_name: str, report: dict) -> GateResult:
    test_name = REQUIRED_TEST_NAMES[gate_name]
    found, passed = check_named_test(report, test_name)
    if not found:
        return GateResult(
            gate=gate_name, status="FAIL", evidence_tier="A",
            details={"reason": f"required test not found: {test_name}", "required_test": test_name},
        )
    if not passed:
        return GateResult(
            gate=gate_name, status="FAIL", evidence_tier="A",
            details={"reason": f"required test failed: {test_name}", "required_test": test_name},
        )
    return GateResult(
        gate=gate_name, status="PASS", evidence_tier="A",
        details={"required_test": test_name},
    )


def check_position_limit(report: dict) -> GateResult:
    return _check("position-limit", report)


def check_idempotency(report: dict) -> GateResult:
    return _check("idempotency", report)


def check_kill_switch(report: dict) -> GateResult:
    return _check("kill-switch", report)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gates/test_behavioral.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/gates/__init__.py shared/scripts/spotcat_gates/gates/behavioral.py \
  shared/scripts/tests/gates/__init__.py shared/scripts/tests/gates/test_behavioral.py
git commit -m "feat(gates): add P0 behavioral gates (position-limit, idempotency, kill-switch)"
```

---

## Task 6: Credentials gate

**Files:**
- Create: `shared/scripts/spotcat_gates/gates/credentials.py`
- Test: `shared/scripts/tests/gates/test_credentials.py`

**Interfaces:**
- Consumes: `spotcat_gates.result.GateResult` (Task 2).
- Produces: `spotcat_gates.gates.credentials.check_credentials(paths: list[Path]) -> GateResult` — scans the
  given files for hardcoded-secret patterns. Self-contained (no external `gitleaks` binary dependency, per spec
  §2.2's "gitleaks 或等价正则/熵检测" allowance).

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/gates/test_credentials.py`:
```python
from spotcat_gates.gates.credentials import check_credentials


def test_credentials_pass_on_clean_file(tmp_path):
    f = tmp_path / "strategy.py"
    f.write_text("api_key = os.environ['BROKER_API_KEY']\n")
    r = check_credentials([f])
    assert r.status == "PASS"
    assert r.details["scanned_files"] == 1


def test_credentials_fail_on_hardcoded_key(tmp_path):
    f = tmp_path / "strategy.py"
    fake_key = "sk_live_" + "FIXTURE0000000000000EXAMPLE"
    f.write_text(f'api_key = "{fake_key}"\n')
    r = check_credentials([f])
    assert r.status == "FAIL"
    assert str(f) in r.details["findings"][0]["file"]


def test_credentials_fail_on_aws_style_key(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"\n')
    r = check_credentials([f])
    assert r.status == "FAIL"


def test_credentials_error_on_unreadable_file(tmp_path):
    missing = tmp_path / "does-not-exist.py"
    r = check_credentials([missing])
    assert r.status == "ERROR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gates/test_credentials.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.gates.credentials'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/gates/credentials.py`:
```python
from __future__ import annotations

import re
from pathlib import Path

from spotcat_gates.result import GateResult

# Deliberately simple, self-contained patterns — not a full entropy scanner. Extend this list
# rather than reaching for an external binary dependency (spec §2.2 "或等价正则/熵检测").
_PATTERNS = [
    ("stripe-like-secret", re.compile(r"sk_live_[A-Za-z0-9]{20,}")),
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic-assigned-secret", re.compile(
        r"(?i)(api_key|secret|password|token)\s*=\s*[\"'][A-Za-z0-9/+_\-]{16,}[\"']"
    )),
]


def check_credentials(paths: list[Path]) -> GateResult:
    findings = []
    for p in paths:
        p = Path(p)
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
            return GateResult(
                gate="credentials", status="ERROR", evidence_tier="A",
                details={"reason": f"could not read {p}: {e}"},
            )
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in _PATTERNS:
                if pattern.search(line):
                    findings.append({"file": str(p), "line": line_no, "pattern": name})

    if findings:
        return GateResult(
            gate="credentials", status="FAIL", evidence_tier="A",
            details={"findings": findings, "scanned_files": len(paths)},
        )
    return GateResult(
        gate="credentials", status="PASS", evidence_tier="A",
        details={"scanned_files": len(paths)},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gates/test_credentials.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/gates/credentials.py shared/scripts/tests/gates/test_credentials.py
git commit -m "feat(gates): add P0 credentials gate (self-contained pattern scan)"
```

---

## Task 7: Backtest-result schema + data-file resolution helper

**Files:**
- Create: `shared/schemas/backtest-result.schema.json`
- Create: `shared/scripts/spotcat_gates/data_files.py`
- Test: `shared/scripts/tests/test_data_files.py`

**Interfaces:**
- Produces: `spotcat_gates.data_files.resolve_data_files(config: dict) -> list[Path]` — lists files under
  `config["paths"]["data_root"]` whose filename contains an ISO date (`YYYY-MM-DD`) falling within
  `expected_date_range`. Used by both the date-gap gate (Task 8) and the backtest-metrics gate's `data_hash`
  computation (Task 9) — factored out once so both share the same resolution logic (DRY, per spec's own
  emphasis on not inventing parallel definitions of the same thing).
- Produces: `spotcat_gates.data_files.hash_data_files(files: list[Path]) -> str` — SHA-256 over the sorted
  `"relpath:sha256(content)"` lines of each file, hex digest. This is the `data_hash` written into the
  regularized backtest-result JSON (Task 9).
- Produces: `spotcat_gates.data_files.missing_dates(config: dict, files: list[Path]) -> list[str]` — ISO dates
  in the expected range with no matching file.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/test_data_files.py`:
```python
import hashlib

from spotcat_gates.data_files import hash_data_files, missing_dates, resolve_data_files


def _config(data_root, start, end):
    return {
        "paths": {
            "data_root": str(data_root),
            "data_format": "csv",
            "expected_date_range": {"start": start, "end": end},
        }
    }


def test_resolve_data_files_filters_by_date_range(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-02.csv").write_text("b")
    (tmp_path / "2023-12-31.csv").write_text("c")  # outside range
    cfg = _config(tmp_path, "2024-01-01", "2024-01-02")
    files = resolve_data_files(cfg)
    assert sorted(f.name for f in files) == ["2024-01-01.csv", "2024-01-02.csv"]


def test_missing_dates_reports_gap(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-03.csv").write_text("c")
    cfg = _config(tmp_path, "2024-01-01", "2024-01-03")
    files = resolve_data_files(cfg)
    assert missing_dates(cfg, files) == ["2024-01-02"]


def test_missing_dates_empty_when_complete(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-02.csv").write_text("b")
    cfg = _config(tmp_path, "2024-01-01", "2024-01-02")
    files = resolve_data_files(cfg)
    assert missing_dates(cfg, files) == []


def test_hash_data_files_deterministic_and_content_sensitive(tmp_path):
    f1 = tmp_path / "2024-01-01.csv"
    f1.write_text("a")
    f2 = tmp_path / "2024-01-02.csv"
    f2.write_text("b")

    h1 = hash_data_files([f1, f2])
    h2 = hash_data_files([f2, f1])  # order must not matter
    assert h1 == h2

    f1.write_text("changed")
    h3 = hash_data_files([f1, f2])
    assert h3 != h1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_files.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.data_files'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/data_files.py`:
```python
from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_range(config: dict) -> tuple[date, date]:
    rng = config["paths"]["expected_date_range"]
    start = date.fromisoformat(rng["start"])
    end_raw = rng["end"]
    end = date.today() if end_raw == "auto" else date.fromisoformat(end_raw)
    return start, end


def resolve_data_files(config: dict) -> list[Path]:
    start, end = _parse_range(config)
    root = Path(config["paths"]["data_root"])
    if not root.is_dir():
        return []
    out = []
    for f in root.iterdir():
        if not f.is_file():
            continue
        m = _DATE_RE.search(f.name)
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        if start <= d <= end:
            out.append(f)
    return sorted(out)


def missing_dates(config: dict, files: list[Path]) -> list[str]:
    start, end = _parse_range(config)
    present = set()
    for f in files:
        m = _DATE_RE.search(f.name)
        if m:
            present.add(m.group(1))

    missing = []
    d = start
    while d <= end:
        iso = d.isoformat()
        if iso not in present:
            missing.append(iso)
        d += timedelta(days=1)
    return missing


def hash_data_files(files: list[Path]) -> str:
    lines = []
    for f in sorted(files, key=lambda p: p.name):
        content_hash = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        lines.append(f"{Path(f).name}:{content_hash}")
    combined = "\n".join(sorted(lines))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_files.py -v`
Expected: 4 passed

- [ ] **Step 5: Write the backtest-result schema**

`shared/schemas/backtest-result.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SpotCat regularized backtest result",
  "type": "object",
  "required": [
    "sharpe_ratio", "max_drawdown", "win_rate", "trade_count", "profit_factor",
    "in_sample_sharpe", "out_sample_sharpe", "lookahead_check", "data_hash", "generated_at"
  ],
  "additionalProperties": false,
  "properties": {
    "sharpe_ratio": {"type": "number"},
    "max_drawdown": {"type": "number", "minimum": 0},
    "win_rate": {"type": "number", "minimum": 0, "maximum": 1},
    "trade_count": {"type": "integer", "minimum": 0},
    "profit_factor": {"type": "number"},
    "in_sample_sharpe": {"type": "number"},
    "out_sample_sharpe": {"type": "number"},
    "lookahead_check": {"type": "string", "enum": ["not_run", "pass", "fail"]},
    "data_hash": {"type": "string", "minLength": 1},
    "generated_at": {"type": "string", "format": "date-time"}
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add shared/scripts/spotcat_gates/data_files.py shared/scripts/tests/test_data_files.py \
  shared/schemas/backtest-result.schema.json
git commit -m "feat(gates): add data-file resolution/hash helper + backtest-result schema"
```

---

## Task 8: Date-gap pre-check gate

**Files:**
- Create: `shared/scripts/spotcat_gates/gates/date_gap.py`
- Test: `shared/scripts/tests/gates/test_date_gap.py`

**Interfaces:**
- Consumes: `spotcat_gates.data_files.resolve_data_files`, `missing_dates` (Task 7);
  `spotcat_gates.result.GateResult` (Task 2).
- Produces: `spotcat_gates.gates.date_gap.check_date_gap(config: dict) -> GateResult` — `FAIL` if any date in the
  expected range has no file; `PASS` otherwise. This is `gate_runner.py`'s P1 pre-check — its `FAIL` short-
  circuits before the backtest-metrics gate runs (Task 11).

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/gates/test_date_gap.py`:
```python
from spotcat_gates.gates.date_gap import check_date_gap


def _config(data_root, start, end):
    return {
        "paths": {
            "data_root": str(data_root),
            "data_format": "csv",
            "expected_date_range": {"start": start, "end": end},
        }
    }


def test_date_gap_pass_when_complete(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    (tmp_path / "2024-01-02.csv").write_text("b")
    r = check_date_gap(_config(tmp_path, "2024-01-01", "2024-01-02"))
    assert r.status == "PASS"


def test_date_gap_fail_when_missing(tmp_path):
    (tmp_path / "2024-01-01.csv").write_text("a")
    r = check_date_gap(_config(tmp_path, "2024-01-01", "2024-01-03"))
    assert r.status == "FAIL"
    assert r.details["missing_dates"] == ["2024-01-02", "2024-01-03"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gates/test_date_gap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.gates.date_gap'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/gates/date_gap.py`:
```python
from __future__ import annotations

from spotcat_gates.data_files import missing_dates, resolve_data_files
from spotcat_gates.result import GateResult


def check_date_gap(config: dict) -> GateResult:
    files = resolve_data_files(config)
    gaps = missing_dates(config, files)
    if gaps:
        return GateResult(
            gate="date-gap", status="FAIL", evidence_tier="A",
            details={"missing_dates": gaps, "files_found": len(files)},
        )
    return GateResult(
        gate="date-gap", status="PASS", evidence_tier="A",
        details={"files_found": len(files)},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gates/test_date_gap.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/gates/date_gap.py shared/scripts/tests/gates/test_date_gap.py
git commit -m "feat(gates): add P1 date-gap pre-check gate"
```

---

## Task 9: Backtest-metrics gate (parse real numbers, distinguish ERROR from FAIL)

**Files:**
- Create: `shared/scripts/spotcat_gates/gates/backtest_metrics.py`
- Test: `shared/scripts/tests/gates/test_backtest_metrics.py`

**Interfaces:**
- Consumes: `spotcat_gates.data_files.resolve_data_files`, `hash_data_files` (Task 7);
  `spotcat_gates.result.GateResult` (Task 2); `jsonschema`.
- Produces: `spotcat_gates.gates.backtest_metrics.check_backtest_metrics(config: dict, project_root: Path) -> GateResult` —
  runs `config["commands"]["backtest"]`, loads the JSON it wrote, validates against
  `backtest-result.schema.json`, checks thresholds (`min_sharpe`, `max_drawdown`, `min_trades`,
  `max_oos_is_gap_pct`), verifies `data_hash` matches `hash_data_files(resolve_data_files(config))`.
  `status="ERROR"` for anything that means "we could not determine the numbers" (command crashed, output
  missing, output fails schema validation). `status="FAIL"` only for "we got real numbers and they don't meet
  the bar" (including a `data_hash` mismatch, which means the data changed since the result was produced).

**Backtest output file convention locked in for this task:** the project's `backtest` command writes its
regularized-schema JSON to `.spotcat/last-backtest-result.json` (relative to `project_root`) — matching the
example in `shared/config.example.yml`'s `commands.backtest`.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/gates/test_backtest_metrics.py`:
```python
import json

from spotcat_gates.data_files import hash_data_files, resolve_data_files
from spotcat_gates.gates.backtest_metrics import check_backtest_metrics


def _config(project_root, data_root):
    return {
        "paths": {
            "data_root": str(data_root),
            "data_format": "csv",
            "expected_date_range": {"start": "2024-01-01", "end": "2024-01-01"},
        },
        "commands": {"test": "true", "backtest": "python -c \"pass\""},
        "thresholds": {
            "min_sharpe": 1.0, "max_drawdown": 0.2, "min_trades": 10, "max_oos_is_gap_pct": 50,
        },
    }


def _write_result(project_root, data_hash, **overrides):
    result = {
        "sharpe_ratio": 1.5, "max_drawdown": 0.1, "win_rate": 0.55, "trade_count": 40,
        "profit_factor": 1.3, "in_sample_sharpe": 1.6, "out_sample_sharpe": 1.4,
        "lookahead_check": "not_run", "data_hash": data_hash, "generated_at": "2026-08-26T00:00:00Z",
    }
    result.update(overrides)
    out = project_root / ".spotcat" / "last-backtest-result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result), encoding="utf-8")


def test_pass_when_thresholds_met_and_hash_matches(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config))
    _write_result(project_root, data_hash=real_hash)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "PASS"
    assert r.evidence_tier == "A"


def test_fail_when_sharpe_below_threshold(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config))
    _write_result(project_root, data_hash=real_hash, sharpe_ratio=0.2)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "sharpe" in r.details["reason"].lower()


def test_fail_when_data_hash_mismatch(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    _write_result(project_root, data_hash="stale-hash-from-before-data-changed")

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "data_hash" in r.details["reason"]


def test_error_when_output_file_missing(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    config = _config(project_root, data_root)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "ERROR"
    assert "not found" in r.details["reason"]


def test_error_when_output_fails_schema(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    out = project_root / ".spotcat" / "last-backtest-result.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps({"sharpe_ratio": "not-a-number"}), encoding="utf-8")

    config = _config(project_root, data_root)
    r = check_backtest_metrics(config, project_root)
    assert r.status == "ERROR"
    assert "schema" in r.details["reason"]


def test_fail_when_oos_is_gap_too_large(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = _config(project_root, data_root)
    real_hash = hash_data_files(resolve_data_files(config))
    # (2.0 - 0.5) / 2.0 = 75% gap, over the 50% threshold
    _write_result(project_root, data_hash=real_hash, in_sample_sharpe=2.0, out_sample_sharpe=0.5)

    r = check_backtest_metrics(config, project_root)
    assert r.status == "FAIL"
    assert "oos" in r.details["reason"].lower() or "gap" in r.details["reason"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gates/test_backtest_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.gates.backtest_metrics'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/gates/backtest_metrics.py`:
```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema

from spotcat_gates.data_files import hash_data_files, resolve_data_files
from spotcat_gates.result import GateResult

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "backtest-result.schema.json"
_OUTPUT_RELPATH = ".spotcat/last-backtest-result.json"


def check_backtest_metrics(config: dict, project_root: Path) -> GateResult:
    project_root = Path(project_root)
    cmd = config["commands"]["backtest"]
    try:
        subprocess.run(cmd, shell=True, cwd=project_root, timeout=3600)
    except (subprocess.SubprocessError, OSError) as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"backtest command failed to run: {e}"},
        )

    out_path = project_root / _OUTPUT_RELPATH
    if not out_path.is_file():
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"result file not found: {out_path}"},
        )

    try:
        result = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"result file is not valid JSON: {e}"},
        )

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=result, schema=schema)
    except jsonschema.ValidationError as e:
        return GateResult(
            gate="backtest-metrics", status="ERROR", evidence_tier="A",
            details={"reason": f"result failed schema validation: {e.message}"},
        )

    expected_hash = hash_data_files(resolve_data_files(config))
    if result["data_hash"] != expected_hash:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={
                "reason": "data_hash mismatch: data files changed since backtest ran (or wrong data was used)",
                "expected": expected_hash, "got": result["data_hash"],
            },
        )

    th = config["thresholds"]
    if result["sharpe_ratio"] < th["min_sharpe"]:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={"reason": f"sharpe_ratio {result['sharpe_ratio']} < min_sharpe {th['min_sharpe']}"},
        )
    if result["max_drawdown"] > th["max_drawdown"]:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={"reason": f"max_drawdown {result['max_drawdown']} > threshold {th['max_drawdown']}"},
        )
    if result["trade_count"] < th["min_trades"]:
        return GateResult(
            gate="backtest-metrics", status="FAIL", evidence_tier="A",
            details={"reason": f"trade_count {result['trade_count']} < min_trades {th['min_trades']}"},
        )

    is_s, oos_s = result["in_sample_sharpe"], result["out_sample_sharpe"]
    if is_s != 0:
        gap_pct = abs(is_s - oos_s) / abs(is_s) * 100
        if gap_pct > th["max_oos_is_gap_pct"]:
            return GateResult(
                gate="backtest-metrics", status="FAIL", evidence_tier="A",
                details={"reason": f"oos/is gap {gap_pct:.1f}% > threshold {th['max_oos_is_gap_pct']}%"},
            )

    return GateResult(
        gate="backtest-metrics", status="PASS", evidence_tier="A",
        details={k: result[k] for k in (
            "sharpe_ratio", "max_drawdown", "trade_count", "in_sample_sharpe", "out_sample_sharpe"
        )},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gates/test_backtest_metrics.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/gates/backtest_metrics.py shared/scripts/tests/gates/test_backtest_metrics.py
git commit -m "feat(gates): add P1 backtest-metrics gate with ERROR/FAIL separation and data_hash check"
```

---

## Task 10: Lookahead-replay gate

**Files:**
- Create: `shared/scripts/spotcat_gates/gates/lookahead_replay.py`
- Test: `shared/scripts/tests/gates/test_lookahead_replay.py`

**Interfaces:**
- Consumes: `spotcat_gates.result.GateResult` (Task 2).
- Produces: `spotcat_gates.gates.lookahead_replay.check_lookahead_replay(config: dict, project_root: Path) -> GateResult`.

**Design decision locked in for this task** (the spec describes the replay-test *concept* but not its
command-level protocol): the project declares `commands.lookahead_replay`, a command template with a
`{cutoff}` placeholder, e.g. `"python -m strategy.signals --replay-check --data {data_path} --cutoff {cutoff}"`.
The gate runs it twice — once with `paths.replay_check_dates.t`, once with `.t_plus_k` — and each run must print
to stdout a JSON array of `{"timestamp": ..., "signal": ...}` objects sorted by timestamp, covering everything
up to and including `--cutoff`. The gate compares the sub-list of the `t_plus_k` run with `timestamp <= t`
against the full `t` run: they must be identical. A mismatch means the signal at some point in the `t`-cutoff
run changed once more data became visible — i.e. it used data from beyond its own cutoff. If
`replay_check_dates` is absent from config, this gate is skipped (`status="ERROR"`, not silently `PASS` —
absence means "not wired up yet", which must be visible, not mistaken for a clean bill of health).

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/gates/test_lookahead_replay.py`:
```python
import json

from spotcat_gates.gates.lookahead_replay import check_lookahead_replay


def _config(project_root):
    return {
        "paths": {
            "replay_check_dates": {"t": "2024-06-01", "t_plus_k": "2024-06-08"},
        },
        "commands": {
            "lookahead_replay": (
                f"python {project_root / 'replay.py'} --cutoff {{cutoff}}"
            ),
        },
    }


def _write_replay_script(project_root, signals_by_cutoff):
    """signals_by_cutoff: dict[str cutoff] -> list of signal dicts to print for that cutoff."""
    script = project_root / "replay.py"
    script.write_text(
        "import sys, json\n"
        f"TABLE = {json.dumps(signals_by_cutoff)}\n"
        "cutoff = sys.argv[sys.argv.index('--cutoff') + 1]\n"
        "print(json.dumps(TABLE[cutoff]))\n"
    )


def test_pass_when_prefix_identical(tmp_path):
    _write_replay_script(tmp_path, {
        "2024-06-01": [{"timestamp": "2024-06-01T00:00:00", "signal": 1}],
        "2024-06-08": [
            {"timestamp": "2024-06-01T00:00:00", "signal": 1},
            {"timestamp": "2024-06-08T00:00:00", "signal": -1},
        ],
    })
    r = check_lookahead_replay(_config(tmp_path), tmp_path)
    assert r.status == "PASS"


def test_fail_when_prefix_differs(tmp_path):
    _write_replay_script(tmp_path, {
        "2024-06-01": [{"timestamp": "2024-06-01T00:00:00", "signal": 1}],
        "2024-06-08": [
            {"timestamp": "2024-06-01T00:00:00", "signal": -1},  # changed after seeing future data!
            {"timestamp": "2024-06-08T00:00:00", "signal": -1},
        ],
    })
    r = check_lookahead_replay(_config(tmp_path), tmp_path)
    assert r.status == "FAIL"
    assert "2024-06-01T00:00:00" in r.details["reason"]


def test_error_when_replay_check_dates_missing(tmp_path):
    config = {"paths": {}, "commands": {}}
    r = check_lookahead_replay(config, tmp_path)
    assert r.status == "ERROR"
    assert "replay_check_dates" in r.details["reason"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gates/test_lookahead_replay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.gates.lookahead_replay'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/gates/lookahead_replay.py`:
```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from spotcat_gates.result import GateResult


def _run_replay(cmd_template: str, cutoff: str, project_root: Path) -> list[dict]:
    cmd = cmd_template.format(cutoff=cutoff)
    proc = subprocess.run(cmd, shell=True, cwd=project_root, capture_output=True, text=True, timeout=600)
    return json.loads(proc.stdout)


def check_lookahead_replay(config: dict, project_root: Path) -> GateResult:
    dates = config.get("paths", {}).get("replay_check_dates")
    if not dates:
        return GateResult(
            gate="lookahead-replay", status="ERROR", evidence_tier="B",
            details={"reason": "paths.replay_check_dates not configured — gate not wired up"},
        )

    cmd_template = config.get("commands", {}).get("lookahead_replay")
    if not cmd_template:
        return GateResult(
            gate="lookahead-replay", status="ERROR", evidence_tier="B",
            details={"reason": "commands.lookahead_replay not configured — gate not wired up"},
        )

    t, t_plus_k = dates["t"], dates["t_plus_k"]
    try:
        run_t = _run_replay(cmd_template, t, project_root)
        run_t_plus_k = _run_replay(cmd_template, t_plus_k, project_root)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
        return GateResult(
            gate="lookahead-replay", status="ERROR", evidence_tier="B",
            details={"reason": f"replay command failed: {e}"},
        )

    cutoff_t_iso = t + "T23:59:59"
    prefix_from_later_run = [s for s in run_t_plus_k if s["timestamp"] <= cutoff_t_iso]

    if run_t != prefix_from_later_run:
        for a, b in zip(run_t, prefix_from_later_run):
            if a != b:
                return GateResult(
                    gate="lookahead-replay", status="FAIL", evidence_tier="B",
                    details={"reason": f"signal at {a['timestamp']} changed between cutoffs: {a} != {b}"},
                )
        return GateResult(
            gate="lookahead-replay", status="FAIL", evidence_tier="B",
            details={"reason": "signal series length differs between cutoff runs"},
        )

    return GateResult(
        gate="lookahead-replay", status="PASS", evidence_tier="B",
        details={"compared_points": len(run_t)},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gates/test_lookahead_replay.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add shared/scripts/spotcat_gates/gates/lookahead_replay.py shared/scripts/tests/gates/test_lookahead_replay.py
git commit -m "feat(gates): add P1 lookahead-bias displacement replay gate"
```

---

## Task 11: `gate_runner.py` orchestration

**Files:**
- Create: `shared/scripts/spotcat_gates/gate_runner.py`
- Test: `shared/scripts/tests/test_gate_runner.py`

**Interfaces:**
- Consumes: everything from Tasks 1–10 (`load_config`, `ConfigError`, `GateResult`, `new_run_id`,
  `write_gate_output`, `run_test_command`, `TestReportError`, `check_position_limit`, `check_idempotency`,
  `check_kill_switch`, `check_credentials`, `check_date_gap`, `check_backtest_metrics`,
  `check_lookahead_replay`).
- Produces: `spotcat_gates.gate_runner.run_all_gates(config: dict, project_root: Path) -> tuple[list[GateResult], str]` —
  returns `(results, overall_status)`; `overall_status` is `"FAIL"` if any gate is `FAIL`, else `"ERROR"` if any
  gate is `ERROR`, else `"PASS"`.
- Produces: `spotcat_gates.gate_runner.main(argv: list[str] | None = None) -> int` — CLI entrypoint. Exit code
  0 only when `overall_status == "PASS"`.

**Gate order locked in for this task** (P0 always runs first; P1's date-gap is a genuine pre-check — if it
fails, `backtest-metrics` and `lookahead-replay` are skipped rather than run against known-incomplete data,
each recorded as `status="ERROR"` with `"reason": "skipped: date-gap gate failed"` so the output JSON still
accounts for every gate the config declares):

```
credentials -> position-limit -> idempotency -> kill-switch -> date-gap
  -> (if date-gap PASS) backtest-metrics -> lookahead-replay
  -> (if date-gap FAIL) backtest-metrics=ERROR, lookahead-replay=ERROR (skipped, not silently PASS)
```

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/test_gate_runner.py`:
```python
import json
import textwrap

from spotcat_gates.gate_runner import run_all_gates

CONFIG_YAML = textwrap.dedent("""\
    version: 1
    spotcat_schema_version: 1
    paths:
      data_root: {data_root}
      data_format: csv
      expected_date_range: {{ start: "2024-01-01", end: "2024-01-01" }}
    commands:
      test: "python {test_script}"
      backtest: "python {backtest_script}"
    thresholds:
      min_sharpe: 1.0
      max_drawdown: 0.2
      min_trades: 10
      max_oos_is_gap_pct: 50
    code_budget:
      max_file_loc: 500
      ignore_file: .codebudgetignore
    safety:
      paper_only: true
      live_enable_flag_path: .spotcat/LIVE_ENABLED
      global_kill_switch: "~/.spotcat/GLOBAL_LIVE_ENABLE"
      idempotency_key_format: "{{strategy_id}}_{{signal_timestamp}}_{{side}}"
    """)


def _make_pilot_project(tmp_path, all_tests_pass: bool):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "2024-01-01.csv").write_text("x")

    project_root = tmp_path / "project"
    project_root.mkdir()

    outcome = "passed" if all_tests_pass else "failed"
    test_script = project_root / "run_tests.py"
    report_path = project_root / ".spotcat" / "last-test-result.json"
    test_script.write_text(
        "import json, pathlib\n"
        f"pathlib.Path({str(report_path)!r}).parent.mkdir(parents=True, exist_ok=True)\n"
        f"report = {{'tests': ["
        f"{{'nodeid': 'test_x.py::test_position_limit_enforced', 'outcome': {outcome!r}}},"
        f"{{'nodeid': 'test_x.py::test_duplicate_signal_not_double_ordered', 'outcome': {outcome!r}}},"
        f"{{'nodeid': 'test_x.py::test_live_trading_requires_dual_kill_switch', 'outcome': {outcome!r}}},"
        f"]}}\n"
        f"pathlib.Path({str(report_path)!r}).write_text(json.dumps(report))\n"
    )

    from spotcat_gates.data_files import hash_data_files, resolve_data_files
    cfg_for_hash = {
        "paths": {"data_root": str(data_root), "data_format": "csv",
                   "expected_date_range": {"start": "2024-01-01", "end": "2024-01-01"}},
    }
    data_hash = hash_data_files(resolve_data_files(cfg_for_hash))

    backtest_script = project_root / "run_backtest.py"
    result_path = project_root / ".spotcat" / "last-backtest-result.json"
    backtest_result = {
        "sharpe_ratio": 1.5, "max_drawdown": 0.1, "win_rate": 0.55, "trade_count": 40,
        "profit_factor": 1.3, "in_sample_sharpe": 1.6, "out_sample_sharpe": 1.4,
        "lookahead_check": "not_run", "data_hash": data_hash, "generated_at": "2026-08-26T00:00:00Z",
    }
    backtest_script.write_text(
        "import json, pathlib\n"
        f"pathlib.Path({str(result_path)!r}).parent.mkdir(parents=True, exist_ok=True)\n"
        f"pathlib.Path({str(result_path)!r}).write_text(json.dumps({backtest_result!r}))\n"
    )

    config_yaml = CONFIG_YAML.format(
        data_root=data_root, test_script=test_script, backtest_script=backtest_script,
    )
    config_path = project_root / ".spotcat" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_yaml)
    return project_root, config_path


def test_run_all_gates_pass(tmp_path):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=True)
    from spotcat_gates.config import load_config
    config = load_config(config_path)

    results, overall = run_all_gates(config, project_root)
    assert overall == "PASS"
    assert all(r.status == "PASS" for r in results if r.gate != "lookahead-replay")
    # lookahead-replay is ERROR here because replay_check_dates isn't configured in this fixture —
    # that's an expected, visible ERROR, not a silent pass.
    lookahead = next(r for r in results if r.gate == "lookahead-replay")
    assert lookahead.status == "ERROR"


def test_run_all_gates_fail_on_behavioral_test(tmp_path):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=False)
    from spotcat_gates.config import load_config
    config = load_config(config_path)

    results, overall = run_all_gates(config, project_root)
    assert overall == "FAIL"
    position_limit = next(r for r in results if r.gate == "position-limit")
    assert position_limit.status == "FAIL"


def test_main_writes_output_and_returns_nonzero_on_fail(tmp_path, monkeypatch, capsys):
    project_root, config_path = _make_pilot_project(tmp_path, all_tests_pass=False)
    from spotcat_gates.gate_runner import main

    exit_code = main(["--config", str(config_path), "--run-id", "test-run-1"])
    assert exit_code != 0

    out_path = project_root / ".spotcat" / "runs" / "test-run-1" / "gate-output.json"
    assert out_path.is_file()
    payload = json.loads(out_path.read_text())
    assert payload["overall_status"] == "FAIL"
    assert payload["run_id"] == "test-run-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gate_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcat_gates.gate_runner'`

- [ ] **Step 3: Write minimal implementation**

`shared/scripts/spotcat_gates/gate_runner.py`:
```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spotcat_gates.capture import new_run_id, write_gate_output
from spotcat_gates.config import ConfigError, load_config
from spotcat_gates.gates.backtest_metrics import check_backtest_metrics
from spotcat_gates.gates.behavioral import check_idempotency, check_kill_switch, check_position_limit
from spotcat_gates.gates.credentials import check_credentials
from spotcat_gates.gates.date_gap import check_date_gap
from spotcat_gates.gates.lookahead_replay import check_lookahead_replay
from spotcat_gates.result import GateResult
from spotcat_gates.test_report import TestReportError, run_test_command


def run_all_gates(config: dict, project_root: Path) -> tuple[list[GateResult], str]:
    project_root = Path(project_root)
    results: list[GateResult] = []

    strategy_files = list(project_root.rglob("*.py"))
    results.append(check_credentials(strategy_files))

    try:
        report = run_test_command(config, project_root)
    except TestReportError as e:
        err = GateResult(gate="behavioral-tests", status="ERROR", evidence_tier="A", details={"reason": str(e)})
        results.extend([err, err, err])
        report = None

    if report is not None:
        results.append(check_position_limit(report))
        results.append(check_idempotency(report))
        results.append(check_kill_switch(report))

    date_gap_result = check_date_gap(config)
    results.append(date_gap_result)

    if date_gap_result.status == "PASS":
        results.append(check_backtest_metrics(config, project_root))
        results.append(check_lookahead_replay(config, project_root))
    else:
        skipped_detail = {"reason": "skipped: date-gap gate failed"}
        results.append(GateResult(gate="backtest-metrics", status="ERROR", evidence_tier="A", details=skipped_detail))
        results.append(GateResult(gate="lookahead-replay", status="ERROR", evidence_tier="B", details=skipped_detail))

    if any(r.status == "FAIL" for r in results):
        overall = "FAIL"
    elif any(r.status == "ERROR" for r in results):
        overall = "ERROR"
    else:
        overall = "PASS"

    return results, overall


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate-runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 2

    project_root = Path(args.config).resolve().parent.parent  # .spotcat/config.yml -> project root
    run_id = args.run_id or new_run_id()

    results, overall = run_all_gates(config, project_root)
    out_path = write_gate_output(project_root, run_id, results, overall)
    print(f"gate-runner: overall={overall} output={out_path}")

    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gate_runner.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v` (from `shared/scripts/`)
Expected: all tests from Tasks 1–11 pass (roughly 40 tests)

- [ ] **Step 6: Commit**

```bash
git add shared/scripts/spotcat_gates/gate_runner.py shared/scripts/tests/test_gate_runner.py
git commit -m "feat(gates): add gate_runner.py orchestrator (P0 -> P1 pre-check -> P1 metrics/lookahead)"
```

---

## Task 12: Wire gate-runner into the quant-dev skill prompts

**Files:**
- Modify: `skills/spotcat-quant-dev/references/quant-gates.md`
- Modify: `skills/spotcat-quant-dev/references/quant-quality-reviewer-prompt.md`
- Modify: `skills/spotcat-quant-dev/references/quant-scoring.md`
- Modify: `skills/spotcat-quant-dev/references/quant-spec-reviewer-prompt.md`

**Interfaces:**
- Consumes: nothing code-level — this task edits markdown prompt files to point at the CLI built in Task 11
  (`python -m spotcat_gates.gate_runner --config .spotcat/config.yml --run-id <run_id>`) and the JSON it writes
  to `.spotcat/runs/<run_id>/gate-output.json`.

**Integration decision locked in for this task** (this is the open item spotcat-e4 flagged after the design
review — it must be decided now, not left for whoever edits these files next): for every check now covered by
a gate script (P0 safety rules, backtest metrics, date-gap, lookahead bias), **delete** the old prose that told
the agent to "verify" or "check" it manually, and **replace** it with a pointer to the gate JSON. Prose is kept
only for what Task-classification in the spec left to LLM judgment (spec-review's "is the strategy logic
actually correct", scoring's architecture/maintainability dimensions) — those are unaffected by this task.

- [ ] **Step 1: Read the current file to find exact text to replace**

Run: `grep -n "验证无前瞻偏差\|前瞻偏差\|Sharpe\|回撤\|安全检查\|position_limit\|仓位限制\|凭证" skills/spotcat-quant-dev/references/quant-gates.md skills/spotcat-quant-dev/references/quant-quality-reviewer-prompt.md skills/spotcat-quant-dev/references/quant-scoring.md skills/spotcat-quant-dev/references/quant-spec-reviewer-prompt.md`

This step has no fixed expected output — it locates the exact line numbers of prose this task replaces, since
those files were last read (by spotcat-e4, in conversation) rather than by this plan, and line numbers may have
shifted. Use the grep output to build the actual `Edit`/patch for the next step; do not guess line numbers.

- [ ] **Step 2: Add a "自动化门控" section to quant-gates.md**

Insert near the top of `skills/spotcat-quant-dev/references/quant-gates.md`, above the existing Layer 1/2/3
prose:

```markdown
## 自动化门控（gate-runner）

以下检查已脚本化，不再由 agent 手动判断。quality-review 阶段必须先跑：

​```bash
python -m spotcat_gates.gate_runner --config .spotcat/config.yml --run-id <本轮 run_id>
​```

结果写在 `.spotcat/runs/<run_id>/gate-output.json`，agent 读这份文件，不自己复述数字或判断是否达标。

已脚本化（不再需要 agent 手动验证，见文件对应 gate 名）：
- `credentials`：凭证扫描
- `position-limit` / `idempotency` / `kill-switch`：P0 行为性测试是否存在且通过
- `date-gap`：数据日期完整性（P1 前置，失败则 backtest-metrics/lookahead-replay 记为 ERROR 并跳过）
- `backtest-metrics`：Sharpe/回撤/交易次数/样本内外差距，含 data_hash 校验
- `lookahead-replay`：前瞻偏差位移重放测试

`gate-output.json` 里任一 gate 的 `status` 为 `FAIL` 或 `ERROR` = 本轮不得进入 done，退回 implementing 或
root-cause（`ERROR` 通常意味着脚本本身跑不起来或配置没接好，不是"数字不达标"，处理方式不同——见
root-cause-analysis 里新增的第 8 类根因）。
```

- [ ] **Step 3: Delete now-redundant manual-verification prose in quant-gates.md**

Using the line numbers found in Step 1: delete the old Layer 1/2/3 prose lines that described manually checking
credentials, position limits, no-synthetic-data, no-lookahead-bias, Sharpe/drawdown/trade-count thresholds —
these are now covered by the gate list in Step 2. Keep any Layer 1/2/3 prose that is not gate-covered (e.g. if
Layer 1 unit-test prose describes something beyond what `behavioral-tests`/`credentials` gates check).

- [ ] **Step 4: Reorder + rewire quant-quality-reviewer-prompt.md**

Using the line numbers found in Step 1: change the execution order from "读文件→3层门控→打分→安全检查veto→算
总分" to "读文件→跑 gate-runner→读 gate-output.json→P0/P1 门控（`FAIL`/`ERROR`直接veto）→剩余可打分维度（架
构/可维护性/代码风格）→算总分". Delete prose instructing the agent to manually verify safety rules or backtest
numbers; replace with "读 `.spotcat/runs/<run_id>/gate-output.json` 里对应 gate 的 `status`/`details`，不得自
行判断或复述成别的数字。"

- [ ] **Step 5: Update quant-scoring.md**

Using the line numbers found in Step 1: remove scoring-dimension line items that duplicate now-gate-covered
checks (position limits, credentials, backtest thresholds). Leave scoring dimensions that are genuinely
LLM-judgment (architecture/maintainability/code style) untouched.

- [ ] **Step 6: Update quant-spec-reviewer-prompt.md**

Using the line numbers found in Step 1: for any spec-review checklist item that duplicates a now-gate-covered
check, replace it with "此项由 gate-runner 在 quality-review 阶段脚本验证，spec-review 阶段无需重复检查。"
Leave the "策略逻辑是否正确实现" (semantic correctness against acceptance criteria) item untouched — that
remains LLM judgment per the spec's §"只能留给LLM" classification.

- [ ] **Step 7: Verify no orphaned references**

Run: `grep -rn "验证.*前瞻偏差\|手动.*检查.*仓位\|agent.*自行判断.*Sharpe" skills/spotcat-quant-dev/references/`
Expected: no matches (confirms the old self-report language was actually removed, not just supplemented).

- [ ] **Step 8: Commit**

```bash
git add skills/spotcat-quant-dev/references/quant-gates.md \
  skills/spotcat-quant-dev/references/quant-quality-reviewer-prompt.md \
  skills/spotcat-quant-dev/references/quant-scoring.md \
  skills/spotcat-quant-dev/references/quant-spec-reviewer-prompt.md
git commit -m "docs(quant-dev): wire gate-runner into quality-review flow, remove superseded self-report prose"
```

---

## Task 13: End-to-end pilot fixture (synthetic canary)

**Files:**
- Create: `shared/scripts/tests/fixtures/pilot_project/` (synthetic strategy project used as the fixture)
- Test: `shared/scripts/tests/test_pilot_end_to_end.py`

**Interfaces:**
- Consumes: `spotcat_gates.gate_runner.main` (Task 11).
- Produces: nothing new — this is a fixture-driven integration test proving the whole P0+P1+P2 pipeline works
  against a project structure shaped like a real quant project (own `.spotcat/config.yml`, own test suite, own
  backtest command), not just unit-level mocks. This is the closest this plan can get to the spec's "至少一次
  真实 sprint 的 canary 验证" acceptance line without depending on the user's actual (unspecified) production
  strategy code — running against a real project is a manual follow-up noted in this plan's final section, not
  a scripted task.

- [ ] **Step 1: Write the failing test**

`shared/scripts/tests/test_pilot_end_to_end.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pilot_project"


def test_pilot_project_passes_all_gates(tmp_path):
    # copy the fixture so the test doesn't mutate the checked-in fixture directory
    import shutil
    project_root = tmp_path / "pilot_project"
    shutil.copytree(FIXTURE_ROOT, project_root)

    result = subprocess.run(
        [sys.executable, "-m", "spotcat_gates.gate_runner",
         "--config", str(project_root / ".spotcat" / "config.yml"),
         "--run-id", "pilot-canary-1"],
        cwd=project_root, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    out_path = project_root / ".spotcat" / "runs" / "pilot-canary-1" / "gate-output.json"
    payload = json.loads(out_path.read_text())
    assert payload["overall_status"] == "PASS"
    gate_statuses = {g["gate"]: g["status"] for g in payload["gates"]}
    assert gate_statuses["credentials"] == "PASS"
    assert gate_statuses["position-limit"] == "PASS"
    assert gate_statuses["idempotency"] == "PASS"
    assert gate_statuses["kill-switch"] == "PASS"
    assert gate_statuses["date-gap"] == "PASS"
    assert gate_statuses["backtest-metrics"] == "PASS"
    assert gate_statuses["lookahead-replay"] == "PASS"


def test_pilot_project_fails_when_position_limit_test_removed(tmp_path):
    import shutil
    project_root = tmp_path / "pilot_project"
    shutil.copytree(FIXTURE_ROOT, project_root)

    # sabotage: remove the position-limit test to prove the gate actually catches this
    test_file = project_root / "tests" / "test_risk.py"
    text = test_file.read_text()
    text = text.replace("def test_position_limit_enforced", "def _disabled_test_position_limit_enforced")
    test_file.write_text(text)

    result = subprocess.run(
        [sys.executable, "-m", "spotcat_gates.gate_runner",
         "--config", str(project_root / ".spotcat" / "config.yml"),
         "--run-id", "pilot-canary-2"],
        cwd=project_root, capture_output=True, text=True,
    )
    assert result.returncode != 0

    out_path = project_root / ".spotcat" / "runs" / "pilot-canary-2" / "gate-output.json"
    payload = json.loads(out_path.read_text())
    assert payload["overall_status"] == "FAIL"


def test_pilot_project_fails_when_lookahead_bias_introduced(tmp_path):
    import shutil
    project_root = tmp_path / "pilot_project"
    shutil.copytree(FIXTURE_ROOT, project_root)

    # sabotage: make the replay script leak future data into the earlier cutoff's answer
    replay = project_root / "replay.py"
    text = replay.read_text()
    text = text.replace("LEAK_FUTURE = False", "LEAK_FUTURE = True")
    replay.write_text(text)

    result = subprocess.run(
        [sys.executable, "-m", "spotcat_gates.gate_runner",
         "--config", str(project_root / ".spotcat" / "config.yml"),
         "--run-id", "pilot-canary-3"],
        cwd=project_root, capture_output=True, text=True,
    )
    assert result.returncode != 0

    out_path = project_root / ".spotcat" / "runs" / "pilot-canary-3" / "gate-output.json"
    payload = json.loads(out_path.read_text())
    gate_statuses = {g["gate"]: g["status"] for g in payload["gates"]}
    assert gate_statuses["lookahead-replay"] == "FAIL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pilot_end_to_end.py -v`
Expected: FAIL (fixture directory doesn't exist yet — `FileNotFoundError` from `shutil.copytree`)

- [ ] **Step 3: Build the fixture project**

`shared/scripts/tests/fixtures/pilot_project/.spotcat/config.yml`:
```yaml
version: 1
spotcat_schema_version: 1
paths:
  data_root: data
  data_format: csv
  expected_date_range: { start: "2024-06-01", end: "2024-06-08" }
  replay_check_dates: { t: "2024-06-01", t_plus_k: "2024-06-08" }
commands:
  test: "python run_tests.py"
  backtest: "python run_backtest.py"
  lookahead_replay: "python replay.py --cutoff {cutoff}"
thresholds:
  min_sharpe: 1.0
  max_drawdown: 0.2
  min_trades: 5
  max_oos_is_gap_pct: 50
code_budget:
  max_file_loc: 500
  ignore_file: .codebudgetignore
safety:
  paper_only: true
  live_enable_flag_path: .spotcat/LIVE_ENABLED
  global_kill_switch: "~/.spotcat/GLOBAL_LIVE_ENABLE"
  idempotency_key_format: "{strategy_id}_{signal_timestamp}_{side}"
```

`shared/scripts/tests/fixtures/pilot_project/data/2024-06-01.csv` through `2024-06-08.csv`: each one line,
e.g. `date,close\n2024-06-01,100.0\n` (8 files, one per day in range — this is what makes `date-gap` and the
`data_hash` computation real rather than mocked).

`shared/scripts/tests/fixtures/pilot_project/tests/test_risk.py`:
```python
def test_position_limit_enforced():
    max_position = 10
    placed_qty = 8
    assert placed_qty <= max_position


def test_duplicate_signal_not_double_ordered():
    seen_keys = set()
    key = "strat1_2024-06-01T00:00:00_buy"
    first = key not in seen_keys
    seen_keys.add(key)
    second = key not in seen_keys
    assert first is True
    assert second is False


def test_live_trading_requires_dual_kill_switch():
    def would_trade(project_flag: bool, global_flag: bool) -> bool:
        return project_flag and global_flag

    assert would_trade(True, True) is True
    assert would_trade(True, False) is False
    assert would_trade(False, True) is False
    assert would_trade(False, False) is False
```

`shared/scripts/tests/fixtures/pilot_project/run_tests.py`:
```python
import json
import pathlib
import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "--json-report",
     "--json-report-file=.spotcat/last-test-result.json"],
)
# pytest-json-report writes the file itself; nothing else to do here.
sys.exit(0)  # exit 0 regardless — gate_runner reads the report file, not this exit code
```

`shared/scripts/tests/fixtures/pilot_project/run_backtest.py`:
```python
import hashlib
import json
import pathlib

data_dir = pathlib.Path("data")
files = sorted(data_dir.iterdir())
lines = sorted(f"{f.name}:{hashlib.sha256(f.read_bytes()).hexdigest()}" for f in files)
data_hash = hashlib.sha256("\n".join(lines).encode()).hexdigest()

result = {
    "sharpe_ratio": 1.8, "max_drawdown": 0.08, "win_rate": 0.6, "trade_count": 12,
    "profit_factor": 1.5, "in_sample_sharpe": 1.9, "out_sample_sharpe": 1.7,
    "lookahead_check": "not_run", "data_hash": data_hash, "generated_at": "2026-08-26T00:00:00Z",
}
out = pathlib.Path(".spotcat/last-backtest-result.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result))
```

`shared/scripts/tests/fixtures/pilot_project/replay.py`:
```python
import json
import sys

LEAK_FUTURE = False

SIGNALS = [
    {"timestamp": "2024-06-01T00:00:00", "signal": 1},
    {"timestamp": "2024-06-08T00:00:00", "signal": -1},
]


def main():
    cutoff = sys.argv[sys.argv.index("--cutoff") + 1]
    if LEAK_FUTURE:
        # bug: ignores cutoff, always returns the full series regardless of what's "knowable" at cutoff
        visible = SIGNALS
    else:
        visible = [s for s in SIGNALS if s["timestamp"] <= cutoff + "T23:59:59"]
    print(json.dumps(visible))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pilot_end_to_end.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the complete suite one more time**

Run: `pytest -v` (from `shared/scripts/`)
Expected: all tests across Tasks 1–13 pass.

- [ ] **Step 6: Commit**

```bash
git add shared/scripts/tests/fixtures/pilot_project shared/scripts/tests/test_pilot_end_to_end.py
git commit -m "test(gates): add synthetic pilot-project end-to-end canary covering P0+P1+P2"
```

---

## After this plan: manual follow-up (not scripted, out of this plan's scope)

- Run `python -m spotcat_gates.gate_runner` against one of the user's **real** quant projects (per spec §5.4,
  "先在一个真实项目里把 P0-P2 的脚本层跑通、完成至少一次真实 sprint 的 canary"). This requires writing that
  project's own `backtest_command`/`lookahead_replay` adapter to the regularized schema — a one-time,
  project-specific task the spec explicitly does not ask this plan to automate.
- Only after that canary passes does the spec's P3 (vendor-sync distribution) plan become relevant — do not
  start P3 until this happens, per spec §5.4's explicit ordering.
- P4 (LOC budget, PARTIAL/NOT_DONE template field, safety-check-order — the last item is already partly done
  by Task 12 since P0 gates now run before scoring) is a separate follow-up plan.
