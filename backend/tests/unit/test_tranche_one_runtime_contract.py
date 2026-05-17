from pathlib import Path


def test_public_origin_contract_is_documented_in_env_and_runtime_compose() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN" in env_example
    assert "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN" in env_example
    assert "GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN=" in env_example
    assert "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN=" in env_example
    assert "GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN=http://127.0.0.1:8000" not in env_example
    assert "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN=http://127.0.0.1:5173" not in env_example
    assert '${GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN:?GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN must be set}' in compose_text
    assert '${GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN:?GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN must be set}' in compose_text
    assert '${GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN:-http://127.0.0.1:8000}' not in compose_text
    assert '${GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN:-http://127.0.0.1:5173}' not in compose_text


def test_frontend_container_serves_built_assets_instead_of_vite_dev_runtime() -> None:
    dockerfile_text = Path("frontend/Dockerfile").read_text(encoding="utf-8")
    nginx_config = Path("frontend/nginx.conf").read_text(encoding="utf-8")
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "npm run build" in dockerfile_text
    assert "nginx:1.27-alpine" in dockerfile_text
    assert 'CMD ["npm", "run", "dev"' not in dockerfile_text
    assert "proxy_pass http://app:8000;" in nginx_config
    assert "location = /api/sources/sync {" in nginx_config
    assert "proxy_read_timeout 930s;" in nginx_config
    assert 'wget -qO- http://127.0.0.1:5173 >/dev/null || exit 1' in compose_text


