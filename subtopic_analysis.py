import csv
import re
import statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone

INPUT_FILE = "output/youtube_research.csv"
OUTPUT_FILE = "output/subtopic_analysis.csv"

TARGET_FAMILIES = [
    "Visual Physics",
    "General Physics",
    "Quantum Physics",
    "Astrophysics & Space",
]

# These are intentionally broad concept groups.
# A video can belong to more than one subtopic.
SUBTOPICS = {
    "Physics Experiments": [
        "experiment",
        "experiments",
        "demo",
        "demonstration",
        "trick",
        "magic",
        "satisfying science",
    ],

    "Everyday Physics": [
        "everyday",
        "how things work",
        "how it works",
        "why does",
        "why do",
        "physics of",
    ],

    "Magnets & Electricity": [
        "magnet",
        "magnetic",
        "electricity",
        "electric",
        "motor",
        "electromagnet",
        "generator",
    ],

    "Gravity & Motion": [
        "gravity",
        "gravitational",
        "motion",
        "fall",
        "falling",
        "orbit",
        "weightless",
        "weightlessness",
        "acceleration",
    ],

    "Relativity & Spacetime": [
        "relativity",
        "einstein",
        "spacetime",
        "space-time",
        "time dilation",
        "time travel",
        "light speed",
        "speed of light",
        "twin paradox",
    ],

    "Quantum Phenomena": [
        "quantum",
        "quantum physics",
        "quantum mechanics",
        "entanglement",
        "superposition",
        "tunneling",
        "tunnelling",
        "observer effect",
        "double slit",
        "wave function",
        "uncertainty principle",
    ],

    "Dimensions & Reality": [
        "dimension",
        "dimensions",
        "4d",
        "4th dimension",
        "higher dimension",
        "parallel universe",
        "parallel universes",
        "reality",
    ],

    "Black Holes": [
        "black hole",
        "black holes",
        "event horizon",
        "singularity",
        "spaghettification",
    ],

    "Universe & Cosmology": [
        "universe",
        "cosmos",
        "cosmology",
        "big bang",
        "expanding universe",
        "expansion of the universe",
        "origin of the universe",
        "observable universe",
    ],

    "Stars & Extreme Objects": [
        "star",
        "stars",
        "neutron star",
        "neutron stars",
        "supernova",
        "pulsar",
        "white dwarf",
    ],

    "Solar System & Planets": [
        "solar system",
        "planet",
        "planets",
        "earth",
        "mars",
        "jupiter",
        "saturn",
        "venus",
        "mercury",
    ],

    "Scale & Visualization": [
        "how big",
        "how small",
        "scale",
        "zoom",
        "visualization",
        "visual",
        "explained visually",
    ],
}


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def contains_phrase(text, phrase):
    """
    Match phrases as words rather than arbitrary substrings.
    """
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return re.search(pattern, text) is not None


def detect_subtopics(title, description):
    text = f"{title} {description}".lower()

    matches = []

    for subtopic, keywords in SUBTOPICS.items():
        if any(contains_phrase(text, keyword) for keyword in keywords):
            matches.append(subtopic)

    return matches


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


def median(values):
    values = [v for v in values if v is not None]

    if not values:
        return None

    return statistics.median(values)


def lifetime_views_per_day(views, published_at, research_date):
    if views is None:
        return None

    if published_at is None or research_date is None:
        return None

    age_days = (
        research_date - published_at
    ).total_seconds() / 86400

    if age_days <= 0:
        return None

    return views / age_days


def split_families(value):
    if not value:
        return []

    return [
        family.strip()
        for family in value.split(";")
        if family.strip()
    ]


def main():
    now = datetime.now(timezone.utc)

    # subtopic -> family -> cohort -> video_id
    data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(dict)
        )
    )

    # Track all matched videos separately so we can report
    # how frequently each subtopic appears.
    subtopic_all_videos = defaultdict(set)

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:
            video_id = row.get("video_id", "").strip()

            if not video_id:
                continue

            published_at = parse_datetime(
                row.get("published_at")
            )

            if published_at is None:
                continue

            age_days = (
                now - published_at
            ).total_seconds() / 86400

            cohort = classify_cohort(age_days)

            if cohort is None:
                continue

            title = row.get("title", "")
            description = row.get("description", "")

            subtopics = detect_subtopics(
                title,
                description,
            )

            if not subtopics:
                continue

            views = parse_int(row.get("views"))
            duration = parse_float(
                row.get("duration_seconds")
            )

            families = split_families(
                row.get("topic_families")
            )

            velocity = lifetime_views_per_day(
                views,
                published_at,
                now,
            )

            video = {
                "video_id": video_id,
                "title": title,
                "channel_title": row.get(
                    "channel_title",
                    "",
                ),
                "views": views,
                "duration_seconds": duration,
                "velocity": velocity,
            }

            for subtopic in subtopics:
                subtopic_all_videos[
                    subtopic
                ].add(video_id)

                for family in families:

                    if family not in TARGET_FAMILIES:
                        continue

                    data[
                        subtopic
                    ][
                        family
                    ][
                        cohort
                    ][
                        video_id
                    ] = video

    results = []

    for subtopic in SUBTOPICS:

        total_unique = len(
            subtopic_all_videos[subtopic]
        )

        for family in TARGET_FAMILIES:

            cohorts = data[subtopic][family]

            videos_8_30 = list(
                cohorts["8_30"].values()
            )

            videos_31_90 = list(
                cohorts["31_90"].values()
            )

            if not videos_8_30 and not videos_31_90:
                continue

            channels_8_30 = {
                v["channel_title"]
                for v in videos_8_30
                if v["channel_title"]
            }

            channels_31_90 = {
                v["channel_title"]
                for v in videos_31_90
                if v["channel_title"]
            }

            views_8_30 = [
                v["views"]
                for v in videos_8_30
                if v["views"] is not None
            ]

            views_31_90 = [
                v["views"]
                for v in videos_31_90
                if v["views"] is not None
            ]

            velocity_8_30 = [
                v["velocity"]
                for v in videos_8_30
                if v["velocity"] is not None
            ]

            velocity_31_90 = [
                v["velocity"]
                for v in videos_31_90
                if v["velocity"] is not None
            ]

            short_8_30 = sum(
                1
                for v in videos_8_30
                if v["duration_seconds"] is not None
                and v["duration_seconds"] <= 180
            )

            short_31_90 = sum(
                1
                for v in videos_31_90
                if v["duration_seconds"] is not None
                and v["duration_seconds"] <= 180
            )

            long_8_30 = (
                len(videos_8_30)
                - short_8_30
            )

            long_31_90 = (
                len(videos_31_90)
                - short_31_90
            )

            recent_videos = (
                len(videos_8_30)
                + len(videos_31_90)
            )

            if recent_videos >= 40:
                evidence = "Strong"
            elif recent_videos >= 20:
                evidence = "Moderate"
            elif recent_videos >= 10:
                evidence = "Limited"
            else:
                evidence = "Weak"

            results.append({
                "subtopic": subtopic,
                "topic_family": family,
                "unique_videos_all_recent": total_unique,
                "videos_8_30_days": len(
                    videos_8_30
                ),
                "videos_31_90_days": len(
                    videos_31_90
                ),
                "channels_8_30_days": len(
                    channels_8_30
                ),
                "channels_31_90_days": len(
                    channels_31_90
                ),
                "median_views_8_30_days": median(
                    views_8_30
                ),
                "median_views_31_90_days": median(
                    views_31_90
                ),
                "median_lifetime_views_per_day_8_30": median(
                    velocity_8_30
                ),
                "median_lifetime_views_per_day_31_90": median(
                    velocity_31_90
                ),
                "short_candidates_8_30_days": short_8_30,
                "long_candidates_8_30_days": long_8_30,
                "short_candidates_31_90_days": short_31_90,
                "long_candidates_31_90_days": long_31_90,
                "evidence_level": evidence,
            })

    fieldnames = [
        "subtopic",
        "topic_family",
        "unique_videos_all_recent",
        "videos_8_30_days",
        "videos_31_90_days",
        "channels_8_30_days",
        "channels_31_90_days",
        "median_views_8_30_days",
        "median_views_31_90_days",
        "median_lifetime_views_per_day_8_30",
        "median_lifetime_views_per_day_31_90",
        "short_candidates_8_30_days",
        "long_candidates_8_30_days",
        "short_candidates_31_90_days",
        "long_candidates_31_90_days",
        "evidence_level",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in results:
            writer.writerow(row)

    print("\nSubtopic Analysis")
    print("=" * 90)

    # Print strongest subtopics by 31-90 day median views.
    ranked = sorted(
        results,
        key=lambda x: (
            x["median_views_31_90_days"] or 0
        ),
        reverse=True,
    )

    for row in ranked[:20]:
        print(
            f"{row['subtopic']} | "
            f"{row['topic_family']} | "
            f"31-90d median views="
            f"{row['median_views_31_90_days']} | "
            f"videos="
            f"{row['videos_31_90_days']} | "
            f"channels="
            f"{row['channels_31_90_days']}"
        )

    print(
        f"\nSaved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
