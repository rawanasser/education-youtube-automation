
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


def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

    now = datetime.now(timezone.utc)

    groups = defaultdict(list)

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as file:
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
            matched_queries = row.get("matched_queries", "")

            for query in matched_queries.split(";"):
                query = query.strip().lower()

                if query not in TARGET_TOPICS:
                    continue

                published = parse_date(row.get("published_at"))

                if published is None:
                    continue

                age_days = max(
                    (now - published).total_seconds() / 86400,
                    0
                )

                views = number(row.get("views"))
                duration = number(row.get("duration_seconds"))

                if views is None or age_days <= 0:
                    views_per_day = None
                else:
                    views_per_day = views / age_days

                groups[query].append({
                    "published": published,
                    "age_days": age_days,
                    "views": views,
                    "views_per_day": views_per_day,
                    "channel": row.get("channel_title", "").strip(),
                    "format": get_format(duration),
                })

    results = []

    for query, topic_name in TARGET_TOPICS.items():
        videos = groups[query]

        recent_30 = [
            video for video in videos
            if video["age_days"] <= 30
        ]

        recent_90 = [
            video for video in videos
            if video["age_days"] <= 90
        ]

        def valid_median(items, field):
            values = [
                video[field] for video in items
                if video[field] is not None
            ]
            return round(median(values), 2) if values else ""

        results.append({
            "topic": topic_name,
            "total_videos_found": len(videos),
            "videos_last_30_days": len(recent_30),
            "videos_last_90_days": len(recent_90),
            "channels_last_90_days": len({
                video["channel"]
                for video in recent_90
                if video["channel"]
            }),
            "median_views_last_90_days": valid_median(
                recent_90, "views"
            ),
            "median_views_per_day_last_90_days": valid_median(
                recent_90, "views_per_day"
            ),
            "short_candidates_last_90_days": sum(
                video["format"] == "short_form_candidate"
                for video in recent_90
            ),
            "long_candidates_last_90_days": sum(
                video["format"] == "long_form_candidate"
                for video in recent_90
            ),
            "evidence_note": (
                "Insufficient recent sample"
                if len(recent_90) < 5
                else "Recent sample available; observational only"
            ),
        })

    os.makedirs("output", exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys()
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"Recent topic analysis saved to {OUTPUT_FILE}")

    for result in results:
        print(
            f"{result['topic']}: "
            f"{result['videos_last_30_days']} videos in 30 days, "
            f"{result['videos_last_90_days']} in 90 days"
        )


if __name__ == "__main__":
    main()
