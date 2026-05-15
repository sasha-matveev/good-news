from pathlib import Path
import subprocess
import re


def test_credential_manager_script_loads_without_compile_errors() -> None:
    root = Path(__file__).resolve().parents[3]
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "$ErrorActionPreference='Stop'; . .\\scripts\\credential-manager.ps1; Write-Host loaded",
    ]

    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "loaded" in completed.stdout
    assert completed.stderr == ""


def test_load_dev_secrets_supports_external_dotenv_file() -> None:
    root = Path(__file__).resolve().parents[3]
    secrets_file = root / ".tmp-load-dev-secrets.env"
    try:
        secrets_file.write_text(
            "GOOD_NEWS_APP_MASTER_KEY=file-master-key\n"
            "GOOD_NEWS_POSTGRES_PASSWORD=file-postgres-password\n",
            encoding="utf-8",
        )
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$ErrorActionPreference='Stop'; "
                "Remove-Item Env:GOOD_NEWS_APP_MASTER_KEY -ErrorAction SilentlyContinue; "
                "Remove-Item Env:GOOD_NEWS_POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
                "Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
                f". .\\scripts\\load-dev-secrets.ps1 -SecretsFilePath '{secrets_file}'; "
                "Write-Host \"master=$env:GOOD_NEWS_APP_MASTER_KEY\"; "
                "Write-Host \"postgres=$env:GOOD_NEWS_POSTGRES_PASSWORD\"; "
                "Write-Host \"compose=$env:POSTGRES_PASSWORD\""
            ),
        ]

        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        secrets_file.unlink(missing_ok=True)

    assert completed.returncode == 0, completed.stderr
    assert "master=file-master-key" in completed.stdout
    assert "postgres=file-postgres-password" in completed.stdout
    assert "compose=file-postgres-password" in completed.stdout


def test_load_dev_secrets_preserves_pre_set_values_when_file_fills_missing_keys() -> None:
    root = Path(__file__).resolve().parents[3]
    secrets_file = root / ".tmp-load-dev-secrets-partial.env"
    try:
        secrets_file.write_text(
            "GOOD_NEWS_APP_MASTER_KEY=file-master-key\n"
            "GOOD_NEWS_POSTGRES_PASSWORD=file-postgres-password\n",
            encoding="utf-8",
        )
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$ErrorActionPreference='Stop'; "
                "$env:GOOD_NEWS_APP_MASTER_KEY='preset-master-key'; "
                "Remove-Item Env:GOOD_NEWS_POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
                "Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
                f". .\\scripts\\load-dev-secrets.ps1 -SecretsFilePath '{secrets_file}'; "
                "Write-Host \"master=$env:GOOD_NEWS_APP_MASTER_KEY\"; "
                "Write-Host \"postgres=$env:GOOD_NEWS_POSTGRES_PASSWORD\"; "
                "Write-Host \"compose=$env:POSTGRES_PASSWORD\""
            ),
        ]

        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        secrets_file.unlink(missing_ok=True)

    assert completed.returncode == 0, completed.stderr
    assert "master=preset-master-key" in completed.stdout
    assert "postgres=file-postgres-password" in completed.stdout
    assert "compose=file-postgres-password" in completed.stdout


def test_load_dev_secrets_fails_when_explicit_file_is_missing() -> None:
    root = Path(__file__).resolve().parents[3]
    missing_file = root / ".tmp-missing-load-dev-secrets.env"
    missing_file.unlink(missing_ok=True)
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$ErrorActionPreference='Stop'; "
            "Remove-Item Env:GOOD_NEWS_APP_MASTER_KEY -ErrorAction SilentlyContinue; "
            "Remove-Item Env:GOOD_NEWS_POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
            "Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
            f"$env:GOOD_NEWS_LOCAL_SECRETS_FILE='{missing_file}'; "
            ". .\\scripts\\load-dev-secrets.ps1"
        ),
    ]

    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    normalized_stderr = re.sub(r"\s+", " ", completed.stderr)
    assert f"Explicit local secrets file '{missing_file}' was requested but does not exist." in normalized_stderr
    assert "Current execution context:" in completed.stderr
    assert "Windows Credential Manager is per-user." in completed.stderr


def test_load_dev_secrets_exposes_context_diagnostics_for_operator_mismatch_debugging() -> None:
    root = Path(__file__).resolve().parents[3]
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$ErrorActionPreference='Stop'; "
            "$env:GOOD_NEWS_APP_MASTER_KEY='preset-master-key'; "
            "$env:GOOD_NEWS_POSTGRES_PASSWORD='preset-postgres-password'; "
            ". .\\scripts\\load-dev-secrets.ps1; "
            "$report = Get-GoodNewsSecretLoadDiagnosticReport; "
            "Write-Host $report"
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
    assert "Current execution context:" in completed.stdout
    assert "Windows Credential Manager is per-user." in completed.stdout
    assert "GOOD_NEWS_LOCAL_SECRETS_FILE" in completed.stdout
    assert "good-news/dev/app-master-key" in completed.stdout
    assert "good-news/dev/postgres-password" in completed.stdout


def test_load_dev_secrets_recovers_missing_values_from_selected_runtime_project() -> None:
    root = Path(__file__).resolve().parents[3]
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$ErrorActionPreference='Stop'; "
            "Remove-Item Env:GOOD_NEWS_APP_MASTER_KEY -ErrorAction SilentlyContinue; "
            "Remove-Item Env:GOOD_NEWS_POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
            "Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
            "function Test-GoodNewsCredentialExists { param([string]$TargetName) return $false }; "
            "function docker { "
            "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args) "
            "if ($Args[0] -eq 'ps') { "
            "if (($Args -contains 'label=com.docker.compose.project=custom-runtime') -and ($Args -contains 'label=com.docker.compose.service=content-api-service')) { "
            "'container-123'; return "
            "} "
            "return "
            "} "
            "if ($Args[0] -eq 'inspect') { "
            "'GOOD_NEWS_APP_MASTER_KEY=runtime-master-key'; "
            "'GOOD_NEWS_POSTGRES_PASSWORD=runtime-postgres-password'; "
            "return "
            "} "
            "throw ('unexpected docker args: ' + ($Args -join ' ')) "
            "}; "
            ". .\\scripts\\load-dev-secrets.ps1 -ComposeProjectName 'custom-runtime'; "
            "Write-Host \"master=$env:GOOD_NEWS_APP_MASTER_KEY\"; "
            "Write-Host \"postgres=$env:GOOD_NEWS_POSTGRES_PASSWORD\"; "
            "Write-Host \"compose=$env:POSTGRES_PASSWORD\""
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
    assert "Loaded GOOD_NEWS_APP_MASTER_KEY: yes (from runtime project container env)" in completed.stdout
    assert "master=runtime-master-key" in completed.stdout
    assert "postgres=runtime-postgres-password" in completed.stdout
    assert "compose=runtime-postgres-password" in completed.stdout


def test_load_dev_secrets_uses_runtime_project_recovery_after_explicit_file_miss() -> None:
    root = Path(__file__).resolve().parents[3]
    missing_file = root / ".tmp-runtime-recovery-missing.env"
    missing_file.unlink(missing_ok=True)
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$ErrorActionPreference='Stop'; "
            "Remove-Item Env:GOOD_NEWS_APP_MASTER_KEY -ErrorAction SilentlyContinue; "
            "Remove-Item Env:GOOD_NEWS_POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
            "Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue; "
            "function Test-GoodNewsCredentialExists { param([string]$TargetName) return $false }; "
            "function docker { "
            "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args) "
            "if ($Args[0] -eq 'ps') { 'container-123'; return } "
            "if ($Args[0] -eq 'inspect') { "
            "'GOOD_NEWS_APP_MASTER_KEY=runtime-master-key'; "
            "'GOOD_NEWS_POSTGRES_PASSWORD=runtime-postgres-password'; "
            "return "
            "} "
            "throw ('unexpected docker args: ' + ($Args -join ' ')) "
            "}; "
            ". .\\scripts\\load-dev-secrets.ps1 "
            f"-SecretsFilePath '{missing_file}' "
            "-ComposeProjectName 'good-news-runtime'; "
            "Write-Host \"master=$env:GOOD_NEWS_APP_MASTER_KEY\"; "
            "Write-Host \"postgres=$env:GOOD_NEWS_POSTGRES_PASSWORD\""
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
    assert "master=runtime-master-key" in completed.stdout
    assert "postgres=runtime-postgres-password" in completed.stdout
