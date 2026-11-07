
import re
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

from datetime import datetime, timedelta, timezone
from pathlib import Path

API_KEY = os.environ.get("YOUTUBE_API_KEY")
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "youtube_research.csv"

MAX_RESULTS = 50

# Each family contains several related discovery queries.
TOPIC_FAMILIES = {
    "Visual Physics": [
        "physics explained visually",
        "physics concepts explained with animation",
        "visual physics explanations",
    ],
    "General Physics": [
        "physics explained for beginners",
        "everyday physics explained",
        "how physics works science explained",
    ],
    "Quantum Physics": [
        "quantum physics explained for beginners",
        "quantum mechanics explained visually",
        "quantum phenomena explained",
    ],
    "Astrophysics & Space": [
        "astrophysics explained for beginners",
        "black holes explained science",
        "universe space physics explained",
    ],
    "AI for Beginners": [
        "artificial intelligence explained for beginners",
        "how artificial intelligence works",
        "AI concepts explained educational",
    ],
    "Machine Learning": [
        "machine learning explained for beginners",
        "neural networks explained educational",
        "deep learning explained visually",
    ],
}

API_BASE = "https://www.googleapis.com/youtube/v3"


def parse_duration_seconds(value):
    match = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        value or "",
    )

    if not match:
        return ""

    hours, minutes, seconds = (
        int(part or 0) for part in match.groups()
    )

    return hours * 3600 + minutes * 60 + seconds


def classify_format(duration_seconds):
    if duration_seconds == "":
        return "unknown"

    if duration_seconds <= 180:
        return "short_candidate"

    return "long_form_candidate"


def api_get(endpoint, params):
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is missing.")

    params = {**params, "key": API_KEY}

    url = (
        f"{API_BASE}/{endpoint}?"
        f"{urllib.parse.urlencode(params)}"
    )

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except Exception as exc:
        raise RuntimeError(
            f"YouTube API request failed ({endpoint}): {exc}"
        ) from None


def iso_utc(value):
    return value.isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def add_search_results(
    collected,
    query,
    family,
    search_pass,
    params,
):
    print(
        f"[{search_pass}] [{family}] {query}"
    )

    result = api_get(
        "search",
        {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": MAX_RESULTS,
            "relevanceLanguage": "en",
            "safeSearch": "strict",
            **params,
        },
    )

    items = result.get("items", [])
    added = 0

    for item in items:
        video_id = item.get(
            "id", {}
        ).get("videoId")

        snippet = item.get("snippet", {})

        if not video_id:
            continue

        if video_id not in collected:
            collected[video_id] = {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_title": snippet.get(
                    "channelTitle", ""
                ),
                "published_at": snippet.get(
                    "publishedAt", ""
                ),
                "views": "",
                "likes": "",
                "comments": "",
                "duration_seconds": "",
                "format_candidate": "unknown",
                "matched_queries": set(),
                "discovery_sources": set(),
                "search_passes": set(),
                "topic_families": set(),
                "description": snippet.get(
                    "description", ""
                ),
                "research_date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
            added += 1

        row = collected[video_id]

        row["matched_queries"].add(query)
        row["discovery_sources"].add(query)
        row["search_passes"].add(search_pass)
        row["topic_families"].add(family)

    print(
        f"  Returned: {len(items)}; "
        f"new unique videos: {added}"
    )


def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_API_KEY is missing.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    collected = {}

    now = datetime.now(timezone.utc)

    windows = {
        "historical": {
            "order": "relevance",
        },
        "recent_8_30": {
            "order": "relevance",
            "publishedAfter": iso_utc(
                now - timedelta(days=30)
            ),
            "publishedBefore": iso_utc(
                now - timedelta(days=8)
            ),
        },
        "recent_31_90": {
            "order": "relevance",
            "publishedAfter": iso_utc(
                now - timedelta(days=90)
            ),
            "publishedBefore": iso_utc(
                now - timedelta(days=31)
            ),
        },
    }

    # Search every query in every discovery window.
    for family, queries in TOPIC_FAMILIES.items():
        for query in queries:
            for search_pass, params in windows.items():
                add_search_results(
                    collected,
                    query,
                    family,
                    search_pass,
                    params,
                )

    video_ids = list(collected.keys())

    print(
        f"\nUnique videos collected: {len(video_ids)}"
    )

    # Fetch statistics and duration in batches.
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]

        result = api_get(
            "videos",
            {
                "part": "statistics,contentDetails",
                "id": ",".join(batch),
            },
        )

        returned_ids = set()

        for item in result.get("items", []):
            video_id = item.get("id")
            returned_ids.add(video_id)

            row = collected.get(video_id)

            if row is None:
                continue

            statistics = item.get("statistics", {})
            details = item.get("contentDetails", {})

            row["views"] = statistics.get(
                "viewCount", ""
            )
            row["likes"] = statistics.get(
                "likeCount", ""
            )
            row["comments"] = statistics.get(
                "commentCount", ""
            )

            duration = parse_duration_seconds(
                details.get("duration", "")
            )

            row["duration_seconds"] = duration
            row["format_candidate"] = (
                classify_format(duration)
            )

        missing_ids = set(batch) - returned_ids

        if missing_ids:
            print(
                f"Warning: {len(missing_ids)} videos "
                "had unavailable statistics."
            )

    columns = [
        "video_id",
        "title",
        "channel_title",
        "published_at",
        "views",
        "likes",
        "comments",
        "duration_seconds",
        "format_candidate",
        "matched_queries",
        "description",
        "research_date_utc",
        "discovery_sources",
        "search_passes",
        "topic_families",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns,
        )

        writer.writeheader()

        for row in collected.values():
            output_row = row.copy()

            for field in (
                "matched_queries",
                "discovery_sources",
                "search_passes",
                "topic_families",
            ):
                output_row[field] = "; ".join(
                    sorted(row[field])
                )

            writer.writerow(output_row)

    print("\nResearch complete.")
    print(f"Unique videos: {len(collected)}")

    for search_pass in windows:
        count = sum(
            search_pass in row["search_passes"]
            for row in collected.values()
        )

        print(
            f"{search_pass}: {count} unique videos"
        )

    print("\nTopic family coverage:")

    for family in TOPIC_FAMILIES:
        count = sum(
            family in row["topic_families"]
            for row in collected.values()
        )

        print(f"{family}: {count} videos")

    print(f"\nCSV saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
