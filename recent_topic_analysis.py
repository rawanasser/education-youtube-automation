import csv
import statistics
from collections import defaultdict
from datetime import datetime, timezone

INPUT_FILE = "output/youtube_research.csv"
OUTPUT_FILE = "output/recent_topic_analysis.csv"

TOPIC_FAMILIES = [
    "Visual Physics",
    "General Physics",
    "Quantum Physics",
    "Astrophysics & Space",
    "AI for Beginners",
    "Machine Learning",
]


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def median(values):
    values = [v for v in values if v is not None]

    if not values:
        return None

    return statistics.median(values)


def classify_cohort(age_days):
    if age_days < 0:
        return None

    if age_days <= 7:
        return "0_7"

    if age_days <= 30:
        return "8_30"

    if age_days <= 90:
        return "31_90"

    return None


def calculate_lifetime_views_per_day(views, published_at, research_date):
    if views is None or published_at is None or research_date is None:
        return None

    age_seconds = (research_date - published_at).total_seconds()

    if age_seconds <= 0:
        return None

    age_days = age_seconds / 86400

    return views / age_days


def split_families(value):
    if not value:
        return []

    return [
        family.strip()
        for family in value.split(";")
        if family.strip()
    ]


def format_number(value):
    if value is None:
        return ""

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

        return round(value, 2)

    return value


def main():
    now = datetime.now(timezone.utc)

    # family -> cohort -> video_id -> row
    family_data = {
        family: {
            "0_7": {},
            "8_30": {},
            "31_90": {},
        }
        for family in TOPIC_FAMILIES
    }

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            video_id = row.get("video_id", "").strip()

            if not video_id:
                continue

            published_at = parse_datetime(row.get("published_at"))
            if published_at is None:
                continue

            age_days = (now - published_at).total_seconds() / 86400

            cohort = classify_cohort(age_days)

            if cohort is None:
                continue

            families = split_families(row.get("topic_families"))

            views = parse_int(row.get("views"))
            duration_seconds = parse_float(row.get("duration_seconds"))

            lifetime_velocity = calculate_lifetime_views_per_day(
                views,
                published_at,
                now,
            )

            enriched_row = {
                "video_id": video_id,
                "channel_title": row.get("channel_title", ""),
                "views": views,
                "duration_seconds": duration_seconds,
                "lifetime_views_per_day": lifetime_velocity,
            }

            for family in families:
                if family not in family_data:
                    continue

                # Deduplicate videos within each family.
                family_data[family][cohort][video_id] = enriched_row

    results = []

    for family in TOPIC_FAMILIES:
        data = family_data[family]

        videos_0_7 = list(data["0_7"].values())
        videos_8_30 = list(data["8_30"].values())
        videos_31_90 = list(data["31_90"].values())

        channels_8_30 = {
            video["channel_title"]
            for video in videos_8_30
            if video["channel_title"]
        }

        channels_31_90 = {
            video["channel_title"]
            for video in videos_31_90
            if video["channel_title"]
        }

        channels_8_90 = channels_8_30 | channels_31_90

        views_8_30 = [
            video["views"]
            for video in videos_8_30
            if video["views"] is not None
        ]

        views_31_90 = [
            video["views"]
            for video in videos_31_90
            if video["views"] is not None
        ]

        velocity_8_30 = [
            video["lifetime_views_per_day"]
            for video in videos_8_30
            if video["lifetime_views_per_day"] is not None
        ]

        velocity_31_90 = [
            video["lifetime_views_per_day"]
            for video in videos_31_90
            if video["lifetime_views_per_day"] is not None
        ]

        short_8_30 = sum(
            1
            for video in videos_8_30
            if video["duration_seconds"] is not None
            and video["duration_seconds"] <= 180
        )

        long_8_30 = len(videos_8_30) - short_8_30

        short_31_90 = sum(
            1
            for video in videos_31_90
            if video["duration_seconds"] is not None
            and video["duration_seconds"] <= 180
        )

        long_31_90 = len(videos_31_90) - short_31_90

        total_recent = len(videos_8_30) + len(videos_31_90)

        if total_recent >= 60:
            evidence_level = "Strong recent sample"
        elif total_recent >= 30:
            evidence_level = "Moderate recent sample"
        elif total_recent >= 10:
            evidence_level = "Limited recent sample"
        else:
            evidence_level = "Insufficient recent sample"

        results.append({
            "topic": family,
            "total_videos_found": (
                len(videos_0_7)
                + len(videos_8_30)
                + len(videos_31_90)
            ),
            "videos_0_7_days": len(videos_0_7),
            "videos_8_30_days": len(videos_8_30),
            "videos_31_90_days": len(videos_31_90),
            "channels_8_30_days": len(channels_8_30),
            "channels_31_90_days": len(channels_31_90),
            "channels_8_90_days": len(channels_8_90),
            "median_views_8_30_days": format_number(
                median(views_8_30)
            ),
            "median_lifetime_views_per_day_8_30": format_number(
                median(velocity_8_30)
            ),
            "median_views_31_90_days": format_number(
                median(views_31_90)
            ),
            "median_lifetime_views_per_day_31_90": format_number(
                median(velocity_31_90)
            ),
            "short_candidates_8_30_days": short_8_30,
            "long_candidates_8_30_days": long_8_30,
            "short_candidates_31_90_days": short_31_90,
            "long_candidates_31_90_days": long_31_90,
            "evidence_level": evidence_level,
            "evidence_note": (
                "0-7 day videos are tracked separately but excluded "
                "from performance comparison. 8-30 day videos indicate "
                "early traction; 31-90 day videos provide stronger recent "
                "performance evidence. Metrics are observational and not "
                "predictions. Videos may belong to multiple topic families."
            ),
        })

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

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nRecent Topic Analysis")
    print("=" * 80)

    for result in results:
        print(
            f"{result['topic']}: "
            f"8-30d={result['videos_8_30_days']}, "
            f"31-90d={result['videos_31_90_days']}, "
            f"evidence={result['evidence_level']}"
        )

    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
