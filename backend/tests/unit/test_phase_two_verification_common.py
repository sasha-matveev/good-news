from pathlib import Path
import subprocess


def test_phase_two_html_shell_check_accepts_multiline_curl_output() -> None:
    root = Path(__file__).resolve().parents[3]
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$ErrorActionPreference='Stop'; "
            ". .\\scripts\\validation\\phase2-verification-common.ps1; "
            "$htmlLines = @("
            "'<!doctype html>',"
            "'<html lang=\"en\">',"
            "'  <body>',"
            "'    <div id=\"root\"></div>',"
            "'  </body>',"
            "'</html>'"
            "); "
            "if (-not (Test-GoodNewsAppShellHtml -Html $htmlLines)) { throw 'shell check rejected valid html'; } "
            "Write-Host valid"
        ),
    ]

    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "valid" in completed.stdout
