
import csv
import math
from datetime import datetime, timezone
from pathlib import Path

INPUT_FILE = Path("output/youtube_research.csv")
OUTPUT_FILE = Path("output/ranked_topics.csv")


def number(value):
    try:
        return float(value) if value not in ("", None) else 0.0
    except (TypeError, ValueError):
        return 0.0


def parse_date(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def capped_log_score(value, cap):
    if value <= 0:
        return 0.0
    return min(
        100.0,
        100 * math.log10(1 + value) / math.log10(1 + cap),
    )


def score_video(row, now):
    views = number(row.get("views"))
    likes = number(row.get("likes"))
    comments = number(row.get("comments"))

    published = parse_date(row.get("published_at", ""))

    if published:
        age_days = max(
            1.0,
            (now - published).total_seconds() / 86400,
        )
    else:
        age_days = None

    views_per_day = views / age_days if age_days else 0.0
    engagement_rate = (
        (likes + comments) / views if views > 0 else 0.0
    )

    velocity_score = capped_log_score(views_per_day, 10_000)

    # A high engagement rate from a small audience can be misleading.
    # Keep this score capped and interpret it alongside view count.
    engagement_score = min(
        100.0,
        engagement_rate / 0.05 * 100,
    )

    recency_score = (
        100 * math.exp(-age_days / 365)
        if age_days is not None
        else 0.0
    )

    # This measures historical reach, not search volume or demand.
    historical_reach_score = capped_log_score(
        views,
        10_000_000,
    )

    total_score = (
        0.40 * velocity_score
        + 0.25 * engagement_score
        + 0.20 * recency_score
        + 0.15 * historical_reach_score
    )

    return {
        "video_id": row.get("video_id", ""),
        "title": row.get("title", ""),
        "channel_title": row.get("channel_title", ""),
        "published_at": row.get("published_at", ""),
        "views": int(views),
        "likes": int(likes) if row.get("likes", "") != "" else "",
        "comments": (
            int(comments) if row.get("comments", "") != "" else ""
        ),
        "matched_queries": row.get("matched_queries", ""),
        "description": row.get("description", ""),
        "research_date_utc": row.get("research_date_utc", ""),
        "duration_seconds": row.get("duration_seconds", ""),
        "format_candidate": row.get("format_candidate", "unknown"),
        "age_days": round(age_days, 1) if age_days is not None else "",
        "views_per_day": round(views_per_day, 1),
        "engagement_rate_percent": round(
            engagement_rate * 100, 3
        ),
        "velocity_score": round(velocity_score, 2),
        "engagement_score": round(engagement_score, 2),
        "recency_score": round(recency_score, 2),
        "historical_reach_score": round(
            historical_reach_score, 2
        ),
        "topic_score": round(total_score, 2),
        "score_method": (
            "Heuristic based on observed video metrics; "
            "not a prediction of future performance"
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
        rows = [score_video(row, now) for row in reader]

    rows.sort(
        key=lambda row: row["topic_score"],
        reverse=True,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

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
        "age_days",
        "views_per_day",
        "engagement_rate_percent",
        "velocity_score",
        "engagement_score",
        "recency_score",
        "historical_reach_score",
        "topic_score",
        "score_method",
    ]

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

    if not rows:
        print("No videos were found to rank.")
        return

    print("\nTop 5 ranked videos:")

    for index, row in enumerate(rows[:5], start=1):
        print(
            f"{index}. Score {row['topic_score']} "
            f"| {row['format_candidate']} "
            f"| {row['title']}"
        )


if __name__ == "__main__":
    main()
