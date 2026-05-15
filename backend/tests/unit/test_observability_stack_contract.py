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
    ]

    missing = [path for path in expected_paths if not Path(path).exists()]
    assert missing == []


def test_compose_wires_the_local_observability_profile() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert 'profiles: ["observability"]' in compose_text
    assert "grafana:" in compose_text
    assert "prometheus:" in compose_text
    assert "grafana/grafana-oss" in compose_text
    assert "prom/prometheus" in compose_text
    assert "./infra/observability/grafana/provisioning:/etc/grafana/provisioning:ro" in compose_text
    assert "./infra/observability/grafana/dashboards:/var/lib/grafana/dashboards:ro" in compose_text
    assert "./infra/observability/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro" in compose_text
    assert "./infra/observability/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro" in compose_text


def test_prometheus_scrapes_good_news_app_and_loads_alert_rules() -> None:
    prometheus_text = Path("infra/observability/prometheus/prometheus.yml").read_text(encoding="utf-8")

    assert 'rule_files:' in prometheus_text
    assert '- /etc/prometheus/alerts.yml' in prometheus_text
    assert 'job_name: app' in prometheus_text
    assert 'targets: ["app:8000"]' in prometheus_text
