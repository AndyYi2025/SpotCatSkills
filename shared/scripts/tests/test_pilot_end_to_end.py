import json
import os
import subprocess
import sys
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pilot_project"

# shared/scripts -- the directory containing the spotcat_gates package. spotcat_gates is not
# pip-installed in this environment, so `python -m spotcat_gates.gate_runner` only resolves when
# this directory is on sys.path. We inject it via PYTHONPATH (rather than running the subprocess
# with cwd=SCRIPTS_ROOT) because gate_runner itself must run with cwd=project_root, and because
# the fixture's own run_backtest.py also needs to import spotcat_gates (see its amendment
# comment) -- PYTHONPATH set here propagates to every nested subprocess (gate_runner ->
# run_tests.py / run_backtest.py / replay.py) since none of them override `env`.
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]


def _run_gate_runner(project_root: Path, run_id: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SCRIPTS_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "spotcat_gates.gate_runner",
         "--config", str(project_root / ".spotcat" / "config.yml"),
         "--run-id", run_id],
        cwd=project_root, capture_output=True, text=True, env=env,
    )


def test_pilot_project_passes_all_gates(tmp_path):
    # copy the fixture so the test doesn't mutate the checked-in fixture directory
    import shutil
    project_root = tmp_path / "pilot_project"
    shutil.copytree(FIXTURE_ROOT, project_root)

    result = _run_gate_runner(project_root, "pilot-canary-1")
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

    result = _run_gate_runner(project_root, "pilot-canary-2")
    assert result.returncode != 0

    out_path = project_root / ".spotcat" / "runs" / "pilot-canary-2" / "gate-output.json"
    payload = json.loads(out_path.read_text())
    assert payload["overall_status"] == "FAIL"
    gate_statuses = {g["gate"]: g["status"] for g in payload["gates"]}
    assert gate_statuses["position-limit"] == "FAIL"


def test_pilot_project_fails_when_lookahead_bias_introduced(tmp_path):
    import shutil
    project_root = tmp_path / "pilot_project"
    shutil.copytree(FIXTURE_ROOT, project_root)

    # sabotage: make the replay script leak future data into the earlier cutoff's answer
    replay = project_root / "replay.py"
    text = replay.read_text()
    text = text.replace("LEAK_FUTURE = False", "LEAK_FUTURE = True")
    replay.write_text(text)

    result = _run_gate_runner(project_root, "pilot-canary-3")
    assert result.returncode != 0

    out_path = project_root / ".spotcat" / "runs" / "pilot-canary-3" / "gate-output.json"
    payload = json.loads(out_path.read_text())
    gate_statuses = {g["gate"]: g["status"] for g in payload["gates"]}
    assert gate_statuses["lookahead-replay"] == "FAIL"
