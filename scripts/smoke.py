import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv

root = Path(__file__).resolve().parents[1]
wheels = list((root / "dist").glob("*.whl"))
assert len(wheels) == 1, "Build exactly one wheel first"
with tempfile.TemporaryDirectory(prefix="artifact-smoke-") as temp:
    tmp = Path(temp)
    env = tmp / "venv"
    venv.EnvBuilder(with_pip=True).create(env)
    py = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(py), "-m", "pip", "install", "--no-deps", str(wheels[0])],
        check=True,
        cwd=tmp,
    )
    command = env / (
        "Scripts/sqlite-schema-atlas.exe"
        if os.name == "nt"
        else "bin/sqlite-schema-atlas"
    )
    # Always exercise the installed module from outside the source checkout.
    module_command = [str(py), "-m", "sqlite_schema_atlas"]
    subprocess.run(
        module_command + ["--demo", "--json", "report.json", "--html", "report.html"],
        check=True,
        cwd=tmp,
    )
    # Also check the packaged console launcher. Some Windows hosts block pip's
    # unsigned .exe launcher; do not change host security policy in a smoke test.
    try:
        subprocess.run(
            [str(command), "--demo"], check=True, cwd=tmp, capture_output=True
        )
    except OSError as exc:
        if (
            os.name != "nt"
            or getattr(exc, "winerror", None) != 4551
            or os.environ.get("GITHUB_ACTIONS")
        ):
            raise
        print(
            "LIMITATION: host application control blocked console launcher (4551); installed python -m entrypoint passed"
        )
    data = json.loads((tmp / "report.json").read_text(encoding="utf-8"))
    assert data["synthetic_demo"] is True and data["schema_version"] == 1
    assert "finding_count" in data
    assert "<html" in (tmp / "report.html").read_text(encoding="utf-8")
    failed = subprocess.run(
        module_command + ["--demo", "--json", "report.json"],
        cwd=tmp,
        capture_output=True,
    )
    assert failed.returncode == 2
print("Installed-wheel smoke passed")
