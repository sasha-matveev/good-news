from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.models.post_analysis import PostAnalysis
from app.models.preference_profile import PreferenceProfile
from app.models.source import Source


@dataclass(frozen=True)
class PreferenceProfileView:
    summary: str
    positive_signals: list[str]
    negative_signals: list[str]
    learning_proof: list[str]
    feedback_totals: dict[str, int]


def _top_signal(counts: dict[str, int]) -> tuple[str, int] | None:
    if not counts:
        return None
    top_key, top_count = min(counts.items(), key=lambda item: (-item[1], item[0]))
    return top_key, top_count


def _topic_phrase(topic: str | None) -> str | None:
    if not topic:
        return None
    return topic.replace("-", " ")


def _format_plural(format_name: str | None) -> str | None:
    if not format_name:
        return None
    if format_name == "opinion":
        return "opinion pieces"
    if format_name.endswith("s"):
        return format_name
    return f"{format_name}s"


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return singular
    return plural or f"{singular}s"


def build_preference_profile(session: Session) -> PreferenceProfileView:
    rows = session.execute(
        select(Source.display_name, Feedback.state, PostAnalysis.metadata_json)
        .join_from(Feedback, PostAnalysis, PostAnalysis.post_id == Feedback.post_id, isouter=True)
        .join(Source, Source.id == select_source_id_for_feedback())
    ).all()

    source_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    depth_counts: dict[str, int] = {}
    negative_topic_counts: dict[str, int] = {}
    negative_format_counts: dict[str, int] = {}
    feedback_totals = {
        "interesting": 0,
        "want_to_read": 0,
        "not_interesting": 0,
        "total": 0,
    }

    for source_name, feedback_state, metadata_json in rows:
        metadata = json.loads(metadata_json or "{}")
        if feedback_state in feedback_totals:
            feedback_totals[feedback_state] += 1
            feedback_totals["total"] += 1

        if feedback_state in {"interesting", "want_to_read"}:
            source_counts[source_name or "Unknown source"] = source_counts.get(source_name or "Unknown source", 0) + 1
            for topic in metadata.get("topics", []):
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            if metadata.get("format"):
                format_counts[metadata["format"]] = format_counts.get(metadata["format"], 0) + 1
            depth_val = metadata.get("technical_depth")
            if depth_val and depth_val != "null":
                depth_counts[depth_val] = depth_counts.get(depth_val, 0) + 1
        if feedback_state == "not_interesting":
            for topic in metadata.get("topics", []):
                negative_topic_counts[topic] = negative_topic_counts.get(topic, 0) + 1
            if metadata.get("format"):
                negative_format_counts[metadata["format"]] = negative_format_counts.get(metadata["format"], 0) + 1

    positive_signals: list[str] = []
    negative_signals: list[str] = []

    top_source = _top_signal(source_counts)
    top_topic = _top_signal(topic_counts)
    top_format = _top_signal(format_counts)
    top_depth = _top_signal(depth_counts)
    top_negative_topic = _top_signal(negative_topic_counts)
    top_negative_format = _top_signal(negative_format_counts)

    if top_source:
        positive_signals.append(
            f"{top_source[1]} {_count_label(top_source[1], 'positive signal')} for source {top_source[0]}"
        )
    if top_topic:
        topic_phrase = _topic_phrase(top_topic[0])
        positive_signals.append(
            f"{top_topic[1]} {_count_label(top_topic[1], 'positive signal')} for topic {topic_phrase}"
        )
    if top_format:
        positive_signals.append(
            f"{top_format[1]} {_count_label(top_format[1], 'positive signal')} for format {top_format[0]}"
        )
    if top_depth:
        positive_signals.append(
            f"{top_depth[1]} {_count_label(top_depth[1], 'positive signal')} for {top_depth[0]} technical material"
        )

    if top_negative_topic:
        topic_phrase = _topic_phrase(top_negative_topic[0])
        negative_signals.append(
            f"{top_negative_topic[1]} {_count_label(top_negative_topic[1], 'not-interesting signal')} against topic {topic_phrase}"
        )
    if top_negative_format:
        negative_signals.append(
            f"{top_negative_format[1]} {_count_label(top_negative_format[1], 'not-interesting signal')} against format {top_negative_format[0]}"
        )

    learning_proof = [
        (
            f"{feedback_totals['total']} feedback decisions recorded: "
            f"{feedback_totals['interesting']} interesting, "
            f"{feedback_totals['want_to_read']} want to read, "
            f"{feedback_totals['not_interesting']} not interesting."
        )
    ]

    strongest_positive_parts: list[str] = []
    if top_source:
        strongest_positive_parts.append(f"source {top_source[0]}")
    if top_topic:
        topic_phrase = _topic_phrase(top_topic[0])
        strongest_positive_parts.append(f"topic {topic_phrase}")
    if strongest_positive_parts:
        learning_proof.append(
            f"Strongest positive pull: {' and '.join(strongest_positive_parts)}."
        )

    strongest_negative_parts: list[str] = []
    if top_negative_topic:
        topic_phrase = _topic_phrase(top_negative_topic[0])
        strongest_negative_parts.append(f"topic {topic_phrase}")
    if top_negative_format:
        strongest_negative_parts.append(f"format {top_negative_format[0]}")
    if strongest_negative_parts:
        learning_proof.append(
            f"Strongest negative pull: {' and '.join(strongest_negative_parts)}."
        )

    if feedback_totals["total"] == 0:
        summary = "No feedback yet. Save reactions from the feed to teach this profile what to prioritize."
        learning_proof = ["0 feedback decisions recorded yet."]
    else:
        positive_focus = ""
        if top_topic and top_format and top_source:
            topic_phrase = _topic_phrase(top_topic[0])
            format_phrase = _format_plural(top_format[0])
            positive_focus = f"toward {topic_phrase} {format_phrase} from {top_source[0]}"
        elif top_topic:
            topic_phrase = _topic_phrase(top_topic[0])
            positive_focus = f"toward {topic_phrase} coverage"
        elif top_source:
            positive_focus = f"toward work from {top_source[0]}"

        negative_focus = ""
        if top_negative_format:
            format_phrase = _format_plural(top_negative_format[0])
            negative_focus = f"away from {format_phrase}"
        elif top_negative_topic:
            topic_phrase = _topic_phrase(top_negative_topic[0])
            negative_focus = f"away from {topic_phrase} coverage"

        summary_parts = [f"From {feedback_totals['total']} feedback signals, the profile is learning"]
        if positive_focus:
            summary_parts.append(positive_focus)
        if negative_focus:
            connector = "and" if positive_focus else ""
            summary_parts.append(f"{connector} {negative_focus}".strip())
        summary = " ".join(summary_parts).strip() + "."

    return PreferenceProfileView(
        summary=summary,
        positive_signals=positive_signals,
        negative_signals=negative_signals,
        learning_proof=learning_proof,
        feedback_totals=feedback_totals,
    )


def persist_preference_profile(session: Session, profile: PreferenceProfileView) -> PreferenceProfile:
    record = session.get(PreferenceProfile, 1)
    if record is None:
        record = PreferenceProfile(id=1)
        session.add(record)
    record.summary = profile.summary
    record.metadata_json = json.dumps(
        {
            "positive_signals": profile.positive_signals,
            "negative_signals": profile.negative_signals,
            "learning_proof": profile.learning_proof,
            "feedback_totals": profile.feedback_totals,
        },
        sort_keys=True,
    )
    session.flush()
    return record


def select_source_id_for_feedback():
    # Lazy import to avoid circular dependency: preferences → post → source → preferences
    from app.models.post import Post

    return select(Post.source_id).where(Post.id == Feedback.post_id).scalar_subquery()
