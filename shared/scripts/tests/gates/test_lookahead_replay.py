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
