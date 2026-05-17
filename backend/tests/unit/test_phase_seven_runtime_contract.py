from pathlib import Path


def test_phase_seven_removes_legacy_backend_runtime_shims_and_names() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")
    vite_config = Path("frontend/vite.config.ts").read_text(encoding="utf-8")

    assert "VITE_CONTENT_API_ORIGIN" in compose_text
    assert "VITE_BACKEND_ORIGIN" not in compose_text
    assert "GOOD_NEWS_BACKEND_HOST" not in env_example
    assert "GOOD_NEWS_BACKEND_PORT" not in env_example
    assert "VITE_CONTENT_API_ORIGIN" in vite_config
    assert "VITE_BACKEND_ORIGIN" not in vite_config


def test_phase_seven_uses_monolith_entrypoint() -> None:
    app_main = Path("backend/app/main.py")
    app_startup = Path("backend/scripts/start-app.sh").read_text(encoding="utf-8")

    assert app_main.exists(), "backend/app/main.py must exist as the monolith entrypoint"
    assert "uvicorn app.main:app" in app_startup
