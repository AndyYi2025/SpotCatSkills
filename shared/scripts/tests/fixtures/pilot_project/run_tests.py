import subprocess
import sys

subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "--json-report",
     "--json-report-file=.spotcat/last-test-result.json"],
)
# pytest-json-report writes the file itself; nothing else to do here.
sys.exit(0)  # exit 0 regardless -- gate_runner reads the report file, not this exit code
