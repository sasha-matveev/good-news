from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_phase_two_scripts_and_compose_overrides_exist() -> None:
    expected_paths = [
        "scripts/bootstrap.ps1",
        "scripts/credential-manager.ps1",
        "scripts/load-dev-secrets.ps1",
        "scripts/pull-ollama-model.ps1",
        "scripts/deploy.ps1",
        "scripts/restart-runtime-service.ps1",
        "scripts/validation/phase2-verification-common.ps1",
        "scripts/validation/verify-observability-stack.ps1",
    ]
    deleted_paths = [
        "docker-compose.integration.yml",
        "docker-compose.isolated-acceptance.yml",
        "scripts/deploy-local.ps1",
        "scripts/start-runtime-stack.ps1",
        "scripts/validation/replay-phase2-verification.ps1",
        "scripts/validation/verify-phase2-contract.ps1",
        "scripts/validation/verify-phase2-integration.ps1",
        "scripts/validation/verify-phase2-isolated-acceptance.ps1",
        "scripts/validation/verify-phase2-local.ps1",
        "scripts/validation/verify-phase2-startup-sequencing.ps1",
        "scripts/validation/verify-task6-full-app.ps1",
        "scripts/validation/verify-ws4-local-journey.ps1",
    ]
    deprecated_root_validation_paths = [
        "scripts/phase2-verification-common.ps1",
        "scripts/replay-phase2-verification.ps1",
        "scripts/verify-observability-stack.ps1",
        "scripts/verify-phase2-local.ps1",
        "scripts/verify-phase2-contract.ps1",
        "scripts/verify-phase2-integration.ps1",
        "scripts/verify-phase2-isolated-acceptance.ps1",
        "scripts/verify-phase2-startup-sequencing.ps1",
        "scripts/verify-task6-full-app.ps1",
        "scripts/verify-ws4-local-journey.ps1",
    ]

    missing = [path for path in expected_paths if not (ROOT / path).exists()]
    assert missing == []
    lingering_deleted = [path for path in deleted_paths if (ROOT / path).exists()]
    assert lingering_deleted == []
    lingering_root = [path for path in deprecated_root_validation_paths if (ROOT / path).exists()]
    assert lingering_root == []


def test_phase_two_integration_compose_uses_isolated_host_ports() -> None:
    compose_text = _read("docker-compose.yml")
    common_script = _read("scripts/validation/phase2-verification-common.ps1")

    assert "db-migrate:" in compose_text
    assert 'profiles: ["migration"]' in compose_text
    assert "command: python -m app.core.migration_runner" in compose_text
    assert '${GOOD_NEWS_POSTGRES_HOST_PORT:-5432}:5432' in compose_text
    assert '${GOOD_NEWS_SMTP_UI_HOST_PORT:-8025}:8025' in compose_text
    assert "function Get-GoodNewsAvailableTcpPort" in common_script
    assert "function Invoke-GoodNewsDatabaseMigration" in common_script


def test_phase_two_isolated_acceptance_compose_ports_exist() -> None:
    compose_text = _read("docker-compose.yml")

    assert '${GOOD_NEWS_CONTENT_API_SERVICE_HOST_PORT:-8000}:8000' in compose_text
    assert '${GOOD_NEWS_FRONTEND_HOST_PORT:-5173}:5173' in compose_text
    assert '${GOOD_NEWS_ANALYSIS_SERVICE_HOST_PORT:-8100}:8100' in compose_text
    assert '${GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST_PORT:-8200}:8200' in compose_text
    assert '${GOOD_NEWS_DELIVERY_SERVICE_HOST_PORT:-8300}:8300' in compose_text


def test_deploy_script_sequences_postgres_migration_and_app_services() -> None:
    deploy_text = _read("scripts/deploy.ps1")

    assert 'Invoke-GoodNewsDockerCompose' in deploy_text
    assert '"postgres"' in deploy_text
    assert '"db-migrate"' in deploy_text
    assert 'Wait-ForGoodNewsPostgres' in deploy_text
    assert '"analysis-llm-service"' in deploy_text
    assert '"source-ingestion-service"' in deploy_text
    assert '"delivery-service"' in deploy_text
    assert '"content-api-service"' in deploy_text
    assert '"frontend"' in deploy_text
    assert 'Wait-ForGoodNewsHttpOk' in deploy_text


def test_deploy_script_has_quality_gates_and_skip_option() -> None:
    deploy_text = _read("scripts/deploy.ps1")

    assert '-m pytest' in deploy_text
    assert 'run test' in deploy_text
    assert '-SkipTests' in deploy_text
    assert 'QUALITY GATE' in deploy_text


def test_invoke_good_news_docker_compose_streams_and_captures_output() -> None:
    common_script = _read("scripts/validation/phase2-verification-common.ps1")

    assert "function Invoke-GoodNewsDockerCompose" in common_script
    assert "function Invoke-GoodNewsCompose" in common_script
    assert "Invoke-GoodNewsDockerCompose" in common_script
    assert "$allLines = [System.Collections.Generic.List[string]]::new()" in common_script
    assert "Last 30 lines" in common_script


def test_supported_operator_scripts_default_to_good_news_project() -> None:
    deploy_text = _read("scripts/deploy.ps1")
    restart_text = _read("scripts/restart-runtime-service.ps1")
    pull_text = _read("scripts/pull-ollama-model.ps1")

    assert '$script:ProjectName = "good-news"' in deploy_text
    assert '[string]$ComposeProjectName = "good-news"' in restart_text
    assert '[string]$ComposeProjectName = "good-news"' in pull_text


def test_phase_two_ci_workflow_exists() -> None:
    workflow_text = _read(".github/workflows/verification-foundation.yml")

    assert "owner-local-fast" in workflow_text or "good-news" in workflow_text


def test_operator_scripts_define_canonical_local_deploy_and_restart_flows() -> None:
    deploy_text = _read("scripts/deploy.ps1")
    restart_text = _read("scripts/restart-runtime-service.ps1")
    readme_text = _read("README.md")
    playbook_text = _read("docs/local-operator-playbook.md")

    assert 'load-dev-secrets.ps1' in readme_text
    assert 'deploy.ps1' in readme_text
    assert 'restart-runtime-service.ps1' in readme_text
    assert 'deploy.ps1' in playbook_text
    assert 'restart-runtime-service.ps1' in playbook_text
    assert 'SecretsFilePath' in readme_text
    assert 'Windows Credential Manager is per-user' in readme_text
    assert 'SecretsFilePath' in playbook_text
    assert '-m pytest' in deploy_text
    assert 'run test' in deploy_text
    assert 'Invoke-GoodNewsCompose' in restart_text
    assert 'restart' in restart_text
    assert 'good-news' in restart_text
    assert 'all' in restart_text.lower()


def test_runtime_boot_helper_sequences_postgres_migration_and_runtime_services_explicitly() -> None:
    script_text = _read("scripts/deploy.ps1")

    assert 'param(' in script_text
    assert '[string]$SecretsFilePath = ""' in script_text
    assert '$script:ProjectName = "good-news"' in script_text
    assert '"up", "-d", "--build", "postgres"' in script_text
    assert 'Wait-ForGoodNewsPostgres' in script_text
    assert 'Invoke-GoodNewsDockerCompose' in script_text
    assert '"db-migrate"' in script_text
    assert 'if (-not $env:GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN)' in script_text
    assert 'if (-not $env:GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN)' in script_text
    assert 'load-dev-secrets.ps1' in script_text
    assert '-SecretsFilePath $SecretsFilePath' in script_text
    assert 'Ensure-GoodNewsOllamaModel' in script_text
    assert 'Wait-ForGoodNewsHttpOk' in script_text
