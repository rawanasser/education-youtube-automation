
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

RECENT_DAYS = 90
MAX_RESULTS = 50

QUERIES = [
    "artificial intelligence explained for beginners",
    "machine learning neural networks explained educational",
    "physics explained visually for beginners",
    "quantum computing explained for beginners",
    "astronomy space universe explained educational",
    "planets black holes astrophysics explained",
    "how things work science explained",
]

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


def add_search_results(collected, query, search_pass, params):
    print(f"[{search_pass}] Researching: {query}")

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

    added = 0

    for item in result.get("items", []):
        video_id = item.get("id", {}).get("videoId")
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
                "description": snippet.get(
                    "description", ""
                ),
                "research_date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
            added += 1

        collected[video_id]["matched_queries"].add(query)
        collected[video_id]["discovery_sources"].add(query)
        collected[video_id]["search_passes"].add(search_pass)

    print(
        f"  Results returned: {len(result.get('items', []))}; "
        f"new unique videos: {added}"
    )


def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_API_KEY is missing.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    collected = {}

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)

    published_after = recent_cutoff.isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    # Pass 1: Historical discovery.
    for query in QUERIES:
        add_search_results(
            collected,
            query,
            "historical",
            {
                "order": "relevance",
            },
        )

    # Pass 2: Recent discovery.
    for query in QUERIES:
        add_search_results(
            collected,
            query,
            "recent",
            {
                "order": "date",
                "publishedAfter": published_after,
            },
        )

    video_ids = list(collected.keys())

    print(f"\nUnique videos collected: {len(video_ids)}")

    # Fetch video statistics and durations.
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

            row["views"] = statistics.get("viewCount", "")
            row["likes"] = statistics.get("likeCount", "")
            row["comments"] = statistics.get("commentCount", "")

            duration = parse_duration_seconds(
                details.get("duration", "")
            )

            row["duration_seconds"] = duration
            row["format_candidate"] = classify_format(duration)

        missing_ids = set(batch) - returned_ids

        if missing_ids:
            print(
                f"Warning: {len(missing_ids)} videos "
                "had unavailable statistics."
            )

    # Preserve existing columns and add discovery metadata.
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
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in collected.values():
            output_row = row.copy()

            for field in (
                "matched_queries",
                "discovery_sources",
                "search_passes",
            ):
                output_row[field] = "; ".join(
                    sorted(row[field])
                )

            writer.writerow(output_row)

    historical_count = sum(
        "historical" in row["search_passes"]
        for row in collected.values()
    )

    recent_count = sum(
        "recent" in row["search_passes"]
        for row in collected.values()
    )

    both_count = sum(
        len(row["search_passes"]) == 2
        for row in collected.values()
    )

    print("\nResearch complete.")
    print(f"Unique videos: {len(collected)}")
    print(f"Historical discoveries: {historical_count}")
    print(f"Recent discoveries: {recent_count}")
    print(f"Found in both passes: {both_count}")
    print(f"CSV saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
