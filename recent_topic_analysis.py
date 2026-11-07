import csv
import os
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

INPUT_FILE = "output/youtube_research.csv"
OUTPUT_FILE = "output/recent_topic_analysis.csv"

TARGET_TOPICS = {
    "artificial intelligence explained for beginners": "AI for Beginners",
    "planets black holes astrophysics explained": "Black Holes & Astrophysics",
    "physics explained visually for beginners": "Visual Physics",
}


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_format(duration):
    if duration is None:
        return "unknown"

    if duration <= 180:
        return "short_form_candidate"

    return "long_form_candidate"


def safe_median(items, field):
    values = [
        video[field]
        for video in items
        if video[field] is not None
    ]

    if not values:
        return ""

    return round(median(values), 2)


def count_format(items, format_name):
    return sum(
        video["format"] == format_name
        for video in items
    )


def unique_channels(items):
    return len({
        video["channel"]
        for video in items
        if video["channel"]
    })


def classify_evidence(
    days_8_30,
    days_31_90,
):
    established = len(days_31_90)
    early = len(days_8_30)

    if established >= 10:
        return "Strong recent sample"

    if established >= 5:
        return "Moderate recent sample"

    if established + early >= 5:
        return "Limited recent sample; mostly early-stage videos"

    return "Insufficient recent sample"


def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Missing input: {INPUT_FILE}"
        )

    now = datetime.now(timezone.utc)

    groups = defaultdict(list)

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        required = {
            "published_at",
            "views",
            "duration_seconds",
            "channel_title",
            "matched_queries",
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}"
            )

        for row in reader:
            matched_queries = row.get(
                "matched_queries",
                ""
            )

            for query in matched_queries.split(";"):
                query = query.strip().lower()

                if query not in TARGET_TOPICS:
                    continue

                published = parse_date(
                    row.get("published_at")
                )

                if published is None:
                    continue

                age_days = (
                    now - published
                ).total_seconds() / 86400

                # Ignore future-dated videos caused by clock/API
                # differences.
                if age_days < 0:
                    continue

                views = number(row.get("views"))
                duration = number(
                    row.get("duration_seconds")
                )

                # Lifetime views divided by age.
                # This is a normalized lifetime velocity,
                # NOT recent views gained per day.
                if views is not None and age_days > 0:
                    lifetime_views_per_day = (
                        views / age_days
                    )
                else:
                    lifetime_views_per_day = None

                groups[query].append({
                    "published": published,
                    "age_days": age_days,
                    "views": views,
                    "lifetime_views_per_day":
                        lifetime_views_per_day,
                    "channel": row.get(
                        "channel_title",
                        ""
                    ).strip(),
                    "format": get_format(duration),
                })

    results = []

    for query, topic_name in TARGET_TOPICS.items():
        videos = groups[query]

        # Age cohorts:
        #
        # 0-7 days:
        # Too new for meaningful performance comparison.
        #
        # 8-30 days:
        # Early traction.
        #
        # 31-90 days:
        # Established recent performance.
        #
        too_new = [
            video
            for video in videos
            if 0 <= video["age_days"] <= 7
        ]

        early = [
            video
            for video in videos
            if 7 < video["age_days"] <= 30
        ]

        established = [
            video
            for video in videos
            if 30 < video["age_days"] <= 90
        ]

        recent_90 = early + established

        results.append({
            "topic": topic_name,

            "total_videos_found": len(videos),

            # Age distribution
            "videos_0_7_days": len(too_new),
            "videos_8_30_days": len(early),
            "videos_31_90_days": len(established),

            # Channels
            "channels_8_30_days": unique_channels(early),
            "channels_31_90_days": unique_channels(
                established
            ),
            "channels_8_90_days": unique_channels(
                recent_90
            ),

            # Performance: early traction
            "median_views_8_30_days": safe_median(
                early,
                "views"
            ),
            "median_lifetime_views_per_day_8_30": safe_median(
                early,
                "lifetime_views_per_day"
            ),

            # Performance: established recent
            "median_views_31_90_days": safe_median(
                established,
                "views"
            ),
            "median_lifetime_views_per_day_31_90": safe_median(
                established,
                "lifetime_views_per_day"
            ),

            # Format distribution
            "short_candidates_8_30_days": count_format(
                early,
                "short_form_candidate"
            ),
            "long_candidates_8_30_days": count_format(
                early,
                "long_form_candidate"
            ),

            "short_candidates_31_90_days": count_format(
                established,
                "short_form_candidate"
            ),
            "long_candidates_31_90_days": count_format(
                established,
                "long_form_candidate"
            ),

            # Evidence quality
            "evidence_level": classify_evidence(
                early,
                established
            ),

            "evidence_note": (
                "0-7 day videos are tracked separately "
                "but excluded from performance comparison. "
                "8-30 day videos indicate early traction; "
                "31-90 day videos provide stronger recent "
                "performance evidence. Metrics are "
                "observational and not predictions."
            ),
        })

    os.makedirs("output", exist_ok=True)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        fieldnames = [
            "topic",
            "total_videos_found",

            "videos_0_7_days",
            "videos_8_30_days",
            "videos_31_90_days",

            "channels_8_30_days",
            "channels_31_90_days",
            "channels_8_90_days",

            "median_views_8_30_days",
            "median_lifetime_views_per_day_8_30",

            "median_views_31_90_days",
            "median_lifetime_views_per_day_31_90",

            "short_candidates_8_30_days",
            "long_candidates_8_30_days",

            "short_candidates_31_90_days",
            "long_candidates_31_90_days",

            "evidence_level",
            "evidence_note",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(results)

    print(
        f"Recent topic analysis saved to {OUTPUT_FILE}"
    )

    print()

    for result in results:
        print(
            f"{result['topic']}: "
            f"0-7d={result['videos_0_7_days']}, "
            f"8-30d={result['videos_8_30_days']}, "
            f"31-90d={result['videos_31_90_days']} | "
            f"evidence={result['evidence_level']}"
        )


if __name__ == "__main__":
    main()
