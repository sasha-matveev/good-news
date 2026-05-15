from pathlib import Path


def test_phase_seven_removes_legacy_backend_runtime_shims_and_names() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")
    vite_config = Path("frontend/vite.config.ts").read_text(encoding="utf-8")
    task_six_script = Path("scripts/validation/verify-task6-full-app.ps1").read_text(encoding="utf-8")

    assert "VITE_CONTENT_API_ORIGIN" in compose_text
    assert "VITE_BACKEND_ORIGIN" not in compose_text
    assert "GOOD_NEWS_BACKEND_HOST" not in env_example
    assert "GOOD_NEWS_BACKEND_PORT" not in env_example
    assert "VITE_CONTENT_API_ORIGIN" in vite_config
    assert "VITE_BACKEND_ORIGIN" not in vite_config
    assert "content API posts endpoint" in task_six_script
    assert "Proxy and backend" not in task_six_script


def test_phase_seven_uses_content_api_entrypoint_without_backend_shim() -> None:
    app_main = Path("backend/app/main.py")
    legacy_startup = Path("backend/scripts/start-backend.sh")
    content_api_startup = Path("backend/scripts/start-content-api-service.sh").read_text(encoding="utf-8")

    assert not app_main.exists()
    assert not legacy_startup.exists()
    assert "uvicorn app.content_api_service.main:app" in content_api_startup
