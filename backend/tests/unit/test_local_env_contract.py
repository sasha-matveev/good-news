from pathlib import Path


def test_env_example_and_readme_document_platform_neutral_local_secret_contract() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "GOOD_NEWS_LOCAL_SECRETS_FILE=" in env_example
    assert "GOOD_NEWS_APP_MASTER_KEY=" in env_example
    assert "GOOD_NEWS_POSTGRES_PASSWORD=" in env_example
    assert "platform-neutral local env/secrets contract" in readme_text
    assert "GOOD_NEWS_LOCAL_SECRETS_FILE" in readme_text
    assert "SecretsFilePath" in readme_text
    assert "Windows Credential Manager" in readme_text
    assert "per-user" in readme_text
    assert "optional convenience" in readme_text
