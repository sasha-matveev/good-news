from __future__ import annotations

import app.jobs.source_jobs as source_jobs_module


def test_source_jobs_run_once_passes_analysis_service_client_into_sync(monkeypatch) -> None:
    delegated: dict[str, object] = {}

    class FakeSettings:
        source_failure_threshold = 3

        @classmethod
        def from_env(cls):
            return cls()

    class FakeAnalysisServiceClient:
        def __init__(self, settings) -> None:
            delegated["analysis_service_settings"] = settings

    def fake_create_engine_from_settings(*, settings):
        delegated["engine_settings"] = settings
        return object()

    def fake_create_session_factory(engine):
        delegated["engine"] = engine
        return "session-factory"

    def fake_sync_active_sources(*, session_factory, responses, failure_threshold, analysis_service_client):
        delegated["session_factory"] = session_factory
        delegated["responses"] = responses
        delegated["failure_threshold"] = failure_threshold
        delegated["analysis_service_client"] = analysis_service_client

    monkeypatch.setattr(source_jobs_module, "Settings", FakeSettings)
    monkeypatch.setattr(source_jobs_module, "AnalysisServiceClient", FakeAnalysisServiceClient)
    monkeypatch.setattr(source_jobs_module, "create_engine_from_settings", fake_create_engine_from_settings)
    monkeypatch.setattr(source_jobs_module, "create_session_factory", fake_create_session_factory)
    monkeypatch.setattr(source_jobs_module, "sync_active_sources", fake_sync_active_sources)
    monkeypatch.setattr(source_jobs_module.argparse.ArgumentParser, "parse_args", lambda self: type("Args", (), {"run_once": True})())

    exit_code = source_jobs_module.main()

    assert exit_code == 0
    assert delegated["session_factory"] == "session-factory"
    assert delegated["responses"] == {}
    assert delegated["failure_threshold"] == 3
    assert isinstance(delegated["analysis_service_client"], FakeAnalysisServiceClient)
