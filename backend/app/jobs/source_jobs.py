from __future__ import annotations

import argparse

from app.core.config import Settings
from app.core.db import create_engine_from_settings, create_session_factory
from app.services.analysis_service_client import AnalysisServiceClient
from app.services.source_sync import sync_active_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Run source sync jobs.")
    parser.add_argument("--run-once", action="store_true", help="Run one deterministic source sync cycle.")
    args = parser.parse_args()

    if not args.run_once:
        return 0

    settings = Settings.from_env()
    engine = create_engine_from_settings(settings=settings)
    session_factory = create_session_factory(engine)
    sync_active_sources(
        session_factory=session_factory,
        responses={},
        failure_threshold=settings.source_failure_threshold,
        analysis_service_client=AnalysisServiceClient(settings=settings),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
