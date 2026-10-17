
import csv
import math
from datetime import datetime, timezone
from pathlib import Path

INPUT_FILE = Path("output/youtube_research.csv")
OUTPUT_FILE = Path("output/ranked_topics.csv")

# Base weights. If a metric is unavailable, the remaining weights
# are rescaled proportionally for that video.
WEIGHTS = {
    "velocity_score": 0.40,
    "engagement_score": 0.25,
    "recency_score": 0.20,
    "historical_reach_score": 0.15,
}

VELOCITY_CAP = 10_000
REACH_CAP = 10_000_000
ENGAGEMENT_CAP = 0.05

# Engagement smoothing prevents tiny-view-count videos from
# receiving an extreme score based on very few interactions.
ENGAGEMENT_PRIOR_RATE = 0.02
ENGAGEMENT_PRIOR_VIEWS = 1_000


def number(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


def parse_date(value):
    try:
        date = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def capped_log_score(value, cap):
    if value is None or value <= 0:
        return 0.0
    return min(
        100.0,
        100 * math.log1p(value) / math.log1p(cap),
    )


def classify_format(row):
    duration = number(row.get("duration_seconds"))

    if duration is None:
        return "unknown"

    # Duration is only a format clue, not proof that YouTube
    # classified the original upload as a Short.
    if duration <= 180:
        return "short_form_candidate"

    return "long_form_candidate"


def score_video(row, now):
    views_value = number(row.get("views"))
    views = views_value if views_value is not None else 0.0

    likes = number(row.get("likes"))
    comments = number(row.get("comments"))

    published = parse_date(row.get("published_at", ""))

    if published:
        age_days = max(
            0.0,
            (now - published).total_seconds() / 86400,
        )
    else:
        age_days = None

    views_per_day = (
        views / max(age_days, 1.0)
        if published and views_value is not None
        else None
    )

    # Missing likes/comments are unknown, not zero engagement.
    engagement_available = (
        views > 0 and likes is not None and comments is not None
    )

    if engagement_available:
        raw_engagement_rate = (likes + comments) / views

        # Shrink rates from small audiences toward a 2% prior.
        adjusted_engagement_rate = (
            (likes + comments)
            + ENGAGEMENT_PRIOR_RATE * ENGAGEMENT_PRIOR_VIEWS
        ) / (views + ENGAGEMENT_PRIOR_VIEWS)

        engagement_score = min(
            100.0,
            adjusted_engagement_rate / ENGAGEMENT_CAP * 100,
        )
        engagement_rate_percent = raw_engagement_rate * 100
    else:
        engagement_score = None
        engagement_rate_percent = None

    velocity_score = (
        capped_log_score(views_per_day, VELOCITY_CAP)
        if views_per_day is not None
        else None
    )

    recency_score = (
        100 * math.exp(-age_days / 365)
        if age_days is not None
        else None
    )

    historical_reach_score = (
        capped_log_score(views, REACH_CAP)
        if views_value is not None
        else None
    )

    components = {
        "velocity_score": velocity_score,
        "engagement_score": engagement_score,
        "recency_score": recency_score,
        "historical_reach_score": historical_reach_score,
    }

    available = {
        key: value
        for key, value in components.items()
        if value is not None
    }

    if available:
        total_weight = sum(WEIGHTS[key] for key in available)
        total_score = sum(
            value * WEIGHTS[key] / total_weight
            for key, value in available.items()
        )
    else:
        total_score = 0.0

    return {
        "video_id": row.get("video_id", ""),
        "title": row.get("title", ""),
        "channel_title": row.get("channel_title", ""),
        "published_at": row.get("published_at", ""),
        "views": int(views) if views_value is not None else "",
        "likes": int(likes) if likes is not None else "",
        "comments": int(comments) if comments is not None else "",
        "matched_queries": row.get("matched_queries", ""),
        "description": row.get("description", ""),
        "research_date_utc": row.get("research_date_utc", ""),
        "duration_seconds": row.get("duration_seconds", ""),
        "format_candidate": row.get("format_candidate", "unknown"),
        "format_group": classify_format(row),
        "age_days": round(age_days, 1) if age_days is not None else "",
        "views_per_day": (
            round(views_per_day, 1)
            if views_per_day is not None
            else ""
        ),
        "engagement_rate_percent": (
            round(engagement_rate_percent, 3)
            if engagement_rate_percent is not None
            else ""
        ),
        "velocity_score": (
            round(velocity_score, 2)
            if velocity_score is not None
            else ""
        ),
        "engagement_score": (
            round(engagement_score, 2)
            if engagement_score is not None
            else ""
        ),
        "recency_score": (
            round(recency_score, 2)
            if recency_score is not None
            else ""
        ),
        "historical_reach_score": (
            round(historical_reach_score, 2)
            if historical_reach_score is not None
            else ""
        ),
        "topic_score": round(total_score, 2),
        "format_rank": "",
        "score_method": (
            "Weighted heuristic; available metrics are reweighted "
            "when data is missing; engagement uses a 2% prior "
            "with 1000 prior views; not a prediction"
        ),
    }


def main():
    if not INPUT_FILE.exists():
        raise SystemExit(
            f"Missing {INPUT_FILE}. Run YouTube Research first."
        )

    now = datetime.now(timezone.utc)

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise SystemExit("Input CSV is empty or has no header.")

        required = {
            "video_id",
            "title",
            "published_at",
            "views",
            "duration_seconds",
        }
        missing = required - set(reader.fieldnames)

        if missing:
            raise SystemExit(
                "Input CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )

        rows = [
            score_video(row, now)
            for row in reader
        ]

    # Rank each content format independently.
    format_groups = {}
    for row in rows:
        format_groups.setdefault(row["format_group"], []).append(row)

    for group_rows in format_groups.values():
        group_rows.sort(
            key=lambda row: row["topic_score"],
            reverse=True,
        )

        for rank, row in enumerate(group_rows, start=1):
            row["format_rank"] = rank

    # Preserve a single overall score-sorted CSV.
    rows.sort(
        key=lambda row: row["topic_score"],
        reverse=True,
    )

    columns = [
        "video_id",
        "title",
        "channel_title",
        "published_at",
        "views",
        "likes",
        "comments",
        "matched_queries",
        "description",
        "research_date_utc",
        "duration_seconds",
        "format_candidate",
        "format_group",
        "age_days",
        "views_per_day",
        "engagement_rate_percent",
        "velocity_score",
        "engagement_score",
        "recency_score",
        "historical_reach_score",
        "topic_score",
        "format_rank",
        "score_method",
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Videos scored: {len(rows)}")
    print(f"Ranked results saved to: {OUTPUT_FILE}")

    for group_name in (
        "short_form_candidate",
        "long_form_candidate",
        "unknown",
    ):
        group_rows = [
            row for row in rows
            if row["format_group"] == group_name
        ]

        if not group_rows:
            continue

        print(f"\nTop 5: {group_name}")

        for row in sorted(
            group_rows,
            key=lambda item: item["format_rank"],
        )[:5]:
            print(
                f"{row['format_rank']}. "
                f"Score {row['topic_score']} | "
                f"{row['title']}"
            )


if __name__ == "__main__":
    main()
