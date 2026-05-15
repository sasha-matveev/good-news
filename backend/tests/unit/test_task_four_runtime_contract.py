from pathlib import Path


def test_backend_runtime_runs_alembic_upgrade_before_uvicorn() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    startup_script = Path("backend/scripts/start-app.sh").read_text(encoding="utf-8")
    migration_runner = Path("backend/app/core/migration_runner.py").read_text(encoding="utf-8")
    alembic_ini = Path("backend/alembic.ini").read_text(encoding="utf-8")

    assert "backend/scripts/start-app.sh" in compose_text
    assert "python -m app.core.migration_runner" not in startup_script
    assert "pg_advisory_lock" in migration_runner
    assert "uvicorn app.main:app --host 0.0.0.0 --port" in startup_script
    assert "script_location = %(here)s/alembic" in alembic_ini
    assert "prepend_sys_path = %(here)s" in alembic_ini


def test_compose_uses_app_healthcheck_and_frontend_waits_for_it() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "curl -fsS http://localhost:8000/api/health" in compose_text
    assert "frontend:" in compose_text
    assert "condition: service_healthy" in compose_text


def test_readme_documents_task_four_migration_step_before_compose_boot() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "Task 4 runtime verification" in readme_text
    assert "python -m app.core.migration_runner" in readme_text
    assert "GET /api/posts" in readme_text
