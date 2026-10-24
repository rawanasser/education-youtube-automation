
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

INPUT_FILE = Path("output/ranked_topics.csv")
OUTPUT_FILE = Path("output/topic_opportunities.csv")


def number(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


def median(values):
    valid = [v for v in values if v is not None]
    return statistics.median(valid) if valid else None


def log_score(value, cap):
    if value is None or value <= 0:
        return 0.0
    return min(100.0, 100 * math.log1p(value) / math.log1p(cap))


def split_queries(value):
    if not value:
        return []
    return list(dict.fromkeys(
        item.strip()
        for item in value.split(";")
        if item.strip()
    ))


def analyze_topic(query, rows):
    # Count each video only once per topic.
    unique = {}
    for row in rows:
        video_id = row.get("video_id", "").strip()
        if video_id:
            unique[video_id] = row

    videos = list(unique.values())
    channels = {
        row.get("channel_title", "").strip()
        for row in videos
        if row.get("channel_title", "").strip()
    }

    views = [number(row.get("views")) for row in videos]
    views_day = [number(row.get("views_per_day")) for row in videos]
    engagement = [
        number(row.get("engagement_rate_percent"))
        for row in videos
    ]
    ages = [number(row.get("age_days")) for row in videos]

    median_views = median(views)
    median_views_day = median(views_day)
    median_engagement = median(engagement)
    median_age = median(ages)

    velocity_score = log_score(median_views_day, 50000)
    reach_score = log_score(median_views, 10000000)

    engagement_score = (
        min(100.0, median_engagement / 5 * 100)
        if median_engagement is not None
        else None
    )

    recency_score = (
        100 * math.exp(-median_age / 180)
        if median_age is not None
        else None
    )

    # Reweight only across available metrics.
    components = [
        (velocity_score, 0.40),
        (engagement_score, 0.25),
        (recency_score, 0.20),
        (reach_score, 0.15),
    ]
    available = [
        (score, weight)
        for score, weight in components
        if score is not None
    ]
    weight_sum = sum(weight for _, weight in available)
    base_score = (
        sum(score * weight for score, weight in available) / weight_sum
        if weight_sum else 0.0
    )

    # Reduce confidence when there are few examples or channels.
    video_factor = min(1.0, len(videos) / 5)
    channel_factor = min(1.0, len(channels) / 3)
    confidence = 0.5 + 0.5 * (
        0.6 * video_factor + 0.4 * channel_factor
    )
    opportunity_score = base_score * confidence

    recent_count = sum(
        1 for age in ages if age is not None and age <= 90
    )
    short_count = sum(
        1 for row in videos
        if row.get("format_group") == "short_form_candidate"
    )
    long_count = sum(
        1 for row in videos
        if row.get("format_group") == "long_form_candidate"
    )

    examples = sorted(
        videos,
        key=lambda row: number(row.get("topic_score")) or 0,
        reverse=True,
    )[:3]

    example_titles = " | ".join(
        row.get("title", "").replace("|", "/")
        for row in examples
        if row.get("title", "").strip()
    )

    if len(videos) < 3 or len(channels) < 2:
        evidence = "Low — gather more data"
    elif len(videos) < 5 or len(channels) < 3:
        evidence = "Moderate — limited sample"
    else:
        evidence = "Better sample — still observational"

    return {
        "topic_query": query,
        "videos_analyzed": len(videos),
        "unique_channels": len(channels),
        "median_views": round(median_views, 1) if median_views is not None else "",
        "median_views_per_day": round(median_views_day, 1) if median_views_day is not None else "",
        "median_engagement_rate_percent": round(median_engagement, 3) if median_engagement is not None else "",
        "median_age_days": round(median_age, 1) if median_age is not None else "",
        "videos_published_last_90_days": recent_count,
        "short_form_candidates": short_count,
        "long_form_candidates": long_count,
        "velocity_score": round(velocity_score, 2),
        "engagement_score": round(engagement_score, 2) if engagement_score is not None else "",
        "recency_score": round(recency_score, 2) if recency_score is not None else "",
        "reach_score": round(reach_score, 2),
        "confidence_factor": round(confidence, 3),
        "opportunity_score": round(opportunity_score, 2),
        "evidence_level": evidence,
        "example_videos": example_titles,
        "interpretation": (
            "Heuristic based on sampled videos; not search volume "
            "or a prediction of future performance."
        ),
    }


def main():
    if not INPUT_FILE.exists():
        raise SystemExit(
            f"Missing {INPUT_FILE}. Run the research and scoring scripts first."
        )

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header.")

        required = {
            "video_id", "title", "channel_title",
            "matched_queries", "views",
        }
        missing = required - set(reader.fieldnames)
        if missing:
            raise SystemExit(
                "Missing columns: " + ", ".join(sorted(missing))
            )

        rows = list(reader)

    groups = defaultdict(list)
    for row in rows:
        for query in split_queries(row.get("matched_queries", "")):
            groups[query].append(row)

    results = [
        analyze_topic(query, topic_rows)
        for query, topic_rows in groups.items()
    ]
    results.sort(
        key=lambda row: row["opportunity_score"],
        reverse=True,
    )

    columns = [
        "topic_query", "videos_analyzed", "unique_channels",
        "median_views", "median_views_per_day",
        "median_engagement_rate_percent", "median_age_days",
        "videos_published_last_90_days",
        "short_form_candidates", "long_form_candidates",
        "velocity_score", "engagement_score", "recency_score",
        "reach_score", "confidence_factor", "opportunity_score",
        "evidence_level", "example_videos", "interpretation",
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

    print(f"Topic groups analyzed: {len(results)}")
    print(f"Report saved to: {OUTPUT_FILE}")

    for index, row in enumerate(results[:5], start=1):
        print(
            f"{index}. {row['topic_query']} | "
            f"Score: {row['opportunity_score']} | "
            f"{row['videos_analyzed']} videos | "
            f"{row['evidence_level']}"
        )


if __name__ == "__main__":
    main()
