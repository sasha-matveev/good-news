from pathlib import Path


def test_compose_profiles_and_resource_bounds_reduce_default_local_pressure() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert 'profiles: ["ui"]' in compose_text
    assert 'profiles: ["verification"]' in compose_text
    assert 'profiles: ["ai"]' in compose_text
    assert "mem_limit: 512m" in compose_text
    assert "mem_limit: 256m" in compose_text
    assert "mem_limit: 128m" in compose_text
    assert "mem_limit: 6g" in compose_text
    assert "cpus: 1.0" in compose_text
    assert "cpus: 0.5" in compose_text
    assert "cpus: 0.25" in compose_text
    assert "cpus: 2.0" in compose_text
    assert "max-size: \"10m\"" in compose_text
    assert "max-file: \"3\"" in compose_text


def test_backend_no_longer_requires_ollama_for_default_boot() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "depends_on:" in compose_text
    assert "postgres:" in compose_text
    assert "ollama:\n        condition: service_started" not in compose_text


def test_readme_documents_real_model_default_runtime_and_disposable_stub_lanes() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "Default usable local runtime" in readme_text
    assert ".\\scripts\\deploy.ps1" in readme_text
    assert "analysis-llm-service" in readme_text
    assert "source-ingestion-service" in readme_text
    assert "delivery-service" in readme_text
    assert "content-api-service" in readme_text
    assert "frontend" in readme_text
    assert "docker compose --profile ai up -d ollama" in readme_text
    assert "pulls the configured Ollama model when it is missing" in readme_text


def test_deploy_script_boots_all_services_in_sequence() -> None:
    script_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert '"analysis-llm-service"' in script_text
    assert '"source-ingestion-service"' in script_text
    assert '"delivery-service"' in script_text
    assert '"content-api-service"' in script_text
    assert '"frontend"' in script_text
    assert "Wait-ForGoodNewsPostgres" in script_text
    assert "Wait-ForGoodNewsHttpOk" in script_text


def test_deploy_script_has_retry_and_health_checks() -> None:
    script_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")
    common_text = Path("scripts/validation/phase2-verification-common.ps1").read_text(encoding="utf-8")

    assert "function Wait-ForGoodNewsHttpOk" in common_text
    assert "try {" in common_text
    assert "catch {" in common_text
    assert "Start-Sleep -Seconds 2" in common_text


def test_deploy_script_resolves_origins_and_loads_secrets() -> None:
    script_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert "load-dev-secrets.ps1" in script_text
    assert 'GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN' in script_text
    assert 'GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN' in script_text


def test_deploy_script_sequences_postgres_migration_and_app_services() -> None:
    script_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert 'Invoke-GoodNewsDockerCompose' in script_text
    assert '"db-migrate"' in script_text
    assert '"postgres"' in script_text
    assert 'Wait-ForGoodNewsPostgres' in script_text


def test_deploy_script_handles_feedback_and_ollama_config() -> None:
    script_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")

    assert 'GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON' in script_text
    assert 'GOOD_NEWS_OLLAMA_MODEL' in script_text
