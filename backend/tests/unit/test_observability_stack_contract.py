from pathlib import Path


def test_observability_foundation_files_exist() -> None:
    expected_paths = [
        "infra/observability/grafana/provisioning/datasources/datasources.yml",
        "infra/observability/grafana/provisioning/dashboards/dashboards.yml",
        "infra/observability/grafana/provisioning/alerting/contact-points.yml",
        "infra/observability/grafana/provisioning/alerting/policies.yml",
        "infra/observability/grafana/provisioning/alerting/rules.yml",
        "infra/observability/grafana/dashboards/good-news-overview.json",
        "infra/observability/prometheus/prometheus.yml",
        "infra/observability/prometheus/alerts.yml",
        "infra/observability/loki/config.yml",
        "infra/observability/otel/collector-config.yml",
        "scripts/validation/verify-observability-stack.ps1",
    ]

    missing = [path for path in expected_paths if not Path(path).exists()]
    assert missing == []

    loki_config = Path("infra/observability/loki/config.yml").read_text(encoding="utf-8")
    assert "storage_config:" in loki_config
    assert "filesystem:" in loki_config
    assert "directory: /loki/chunks" in loki_config
    assert "chunks_directory" not in loki_config
    assert "rules_directory" not in loki_config


def test_compose_wires_the_local_observability_profile() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert 'profiles: ["observability"]' in compose_text
    assert "grafana:" in compose_text
    assert "prometheus:" in compose_text
    assert "loki:" in compose_text
    assert "otel-collector:" in compose_text
    assert "grafana-image-renderer:" in compose_text
    assert "grafana/grafana-oss" in compose_text
    assert "prom/prometheus" in compose_text
    assert "grafana/loki" in compose_text
    assert "otel/opentelemetry-collector-contrib" in compose_text
    assert "grafana/grafana-image-renderer" in compose_text
    assert "./infra/observability/grafana/provisioning:/etc/grafana/provisioning:ro" in compose_text
    assert "./infra/observability/grafana/dashboards:/var/lib/grafana/dashboards:ro" in compose_text
    assert "./infra/observability/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro" in compose_text
    assert "./infra/observability/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro" in compose_text
    assert "./infra/observability/loki/config.yml:/etc/loki/config.yml:ro" in compose_text
    assert "./infra/observability/otel/collector-config.yml:/etc/otelcol-contrib/config.yaml:ro" in compose_text


def test_observability_smoke_script_checks_stack_endpoints_and_provisioning() -> None:
    script_text = Path("scripts/validation/verify-observability-stack.ps1").read_text(encoding="utf-8")
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert 'profiles: ["observability"]' in Path("docker-compose.yml").read_text(encoding="utf-8")
    assert '"grafana", "prometheus", "loki", "otel-collector", "grafana-image-renderer"' in script_text
    assert "/api/health" in script_text
    assert "/-/ready" in script_text
    assert "/ready" in script_text
    assert "/metrics" in script_text
    assert "/api/datasources/name/Prometheus" in script_text
    assert "/api/datasources/name/Loki" in script_text
    assert "/api/dashboards/uid/good-news-overview" in script_text
    assert "GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT" in script_text
    assert "Set-GoodNewsPhase2TestSecrets" in script_text
    assert 'GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN' in script_text
    assert 'GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN' in script_text
    assert ".\\scripts\\validation\\verify-observability-stack.ps1" in readme_text
    assert "docker compose --profile observability up -d grafana prometheus loki otel-collector grafana-image-renderer" in readme_text


def test_prometheus_scrapes_good_news_services_and_loads_alert_rules() -> None:
    prometheus_text = Path("infra/observability/prometheus/prometheus.yml").read_text(encoding="utf-8")

    assert 'rule_files:' in prometheus_text
    assert '- /etc/prometheus/alerts.yml' in prometheus_text
    assert 'job_name: content-api-service' in prometheus_text
    assert 'job_name: source-ingestion-service' in prometheus_text
    assert 'job_name: analysis-llm-service' in prometheus_text
    assert 'job_name: delivery-service' in prometheus_text
    assert 'targets: ["content-api-service:8000"]' in prometheus_text
    assert 'targets: ["source-ingestion-service:8200"]' in prometheus_text
    assert 'targets: ["analysis-llm-service:8100"]' in prometheus_text
    assert 'targets: ["delivery-service:8300"]' in prometheus_text
