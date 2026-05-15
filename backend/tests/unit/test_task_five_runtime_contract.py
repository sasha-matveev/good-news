from pathlib import Path


def test_pull_ollama_model_script_loads_dev_secrets_before_compose_exec() -> None:
    script_text = Path("scripts/pull-ollama-model.ps1").read_text(encoding="utf-8")
    helper_text = Path("scripts/validation/phase2-verification-common.ps1").read_text(encoding="utf-8")

    assert '[string]$SecretsFilePath = ""' in script_text
    assert '[string]$ComposeProjectName = "good-news"' in script_text
    assert ". .\\scripts\\load-dev-secrets.ps1" in script_text
    assert '-SecretsFilePath $SecretsFilePath' in script_text
    assert '-ComposeProjectName $ComposeProjectName' in script_text
    assert "Ensure-GoodNewsOllamaModel" in script_text
    assert '"--profile",' in helper_text
    assert '"ai"' in helper_text
    assert '"up"' in helper_text
    assert '"-d"' in helper_text
    assert '"ollama"' in helper_text
    assert '"ollama", "list"' in helper_text.replace("\r\n", "\n")
    assert '"pull"' in helper_text


def test_deploy_and_start_runtime_pass_selected_compose_project_to_secret_loader() -> None:
    deploy_script_text = Path("scripts/deploy.ps1").read_text(encoding="utf-8")
    restart_script_text = Path("scripts/restart-runtime-service.ps1").read_text(encoding="utf-8")

    assert '$script:ProjectName = "good-news"' in deploy_script_text
    assert '-ComposeProjectName $script:ProjectName' in deploy_script_text
    assert '[string]$ComposeProjectName = "good-news"' in restart_script_text


def test_compose_defines_ollama_service_and_backend_runtime_access() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "ollama:" in compose_text
    assert "GOOD_NEWS_OLLAMA_HOST: ollama" in compose_text
    assert "GOOD_NEWS_OLLAMA_PORT: 11434" in compose_text
    assert "GOOD_NEWS_OLLAMA_MODEL" in compose_text
    assert "GOOD_NEWS_OLLAMA_MODEL=llama3.2:3b-instruct-q4_K_M" in env_example
    assert ".\\scripts\\pull-ollama-model.ps1" in readme_text
