from __future__ import annotations

import pytest

from good_news_contract.compare import ContractMismatch, compare_observations
from good_news_contract.model import HttpObservation, ScenarioObservation
from good_news_contract.normalize import Normalizer


def observation(*, state: str, status: int = 200) -> ScenarioObservation:
    return ScenarioObservation(
        http=(HttpObservation(status, None, {"state": state}, None),),
        tables={"feedback": [{"id": 7, "post_id": 1, "state": state}]},
        side_effects=[],
    )


def test_diagnostic_identifies_http_field() -> None:
    with pytest.raises(ContractMismatch) as caught:
        compare_observations(
            "feedback",
            observation(state="interesting"),
            observation(state="not_interesting"),
            Normalizer(frozenset({"id"})),
        )

    assert "$.http[0].body.state" in str(caught.value)


def test_diagnostic_identifies_persisted_row_field() -> None:
    python = ScenarioObservation((), {"feedback": [{"post_id": 1, "state": "interesting"}]}, [])
    java = ScenarioObservation((), {"feedback": [{"post_id": 1, "state": "norm"}]}, [])

    with pytest.raises(ContractMismatch) as caught:
        compare_observations("feedback", python, java, Normalizer(frozenset()))

    assert "$.tables.feedback[0].state" in str(caught.value)


def test_only_allowlisted_volatile_fields_are_normalized() -> None:
    compare_observations(
        "generated-id",
        observation(state="interesting"),
        ScenarioObservation(
            http=(HttpObservation(200, None, {"state": "interesting"}, None),),
            tables={"feedback": [{"id": 99, "post_id": 1, "state": "interesting"}]},
            side_effects=[],
        ),
        Normalizer(frozenset({"id"})),
    )


def test_persisted_json_fields_are_compared_semantically() -> None:
    python = ScenarioObservation((), {"post_analysis": [{"metadata_json": '{"b": 2, "a": 1}'}]}, [])
    java = ScenarioObservation((), {"post_analysis": [{"metadata_json": '{"a":1,"b":2}'}]}, [])

    compare_observations("json", python, java, Normalizer(frozenset()))
