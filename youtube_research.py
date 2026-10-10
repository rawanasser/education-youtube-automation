
import re
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("YOUTUBE_API_KEY")
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "youtube_research.csv"

# Research queries focused on science, physics, space, and AI.
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
    """Convert an ISO 8601 duration to seconds."""
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
    """
    Classify a duration-based format candidate.

    This is a heuristic, not a guarantee that YouTube
    will classify the video as a Short.
    """
    if duration_seconds == "":
        return "unknown"

    if duration_seconds <= 180:
        return "short_candidate"

    return "long_form_candidate"


def api_get(endpoint, params):
    """Call the YouTube Data API without exposing the API key."""
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
        # Never print the request URL because it contains the key.
        raise RuntimeError(
            f"YouTube API request failed ({endpoint}): {exc}"
        ) from None


def main():
    if not API_KEY:
        print(
            "ERROR: YOUTUBE_API_KEY environment variable is missing."
        )
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    collected = {}

    # Step 1: Search for relevant educational videos.
    for query in QUERIES:
        print(f"Researching query: {query}")

        result = api_get(
            "search",
            {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": 10,
                "order": "relevance",
                "relevanceLanguage": "en",
                "safeSearch": "strict",
            },
        )

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
                    "description": snippet.get(
                        "description", ""
                    ),
                    "research_date_utc": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }

            collected[video_id]["matched_queries"].add(query)

    video_ids = list(collected.keys())

    # Step 2: Fetch statistics and duration in batches.
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
            content_details = item.get(
                "contentDetails", {}
            )

            row["views"] = statistics.get(
                "viewCount", ""
            )
            row["likes"] = statistics.get(
                "likeCount", ""
            )
            row["comments"] = statistics.get(
                "commentCount", ""
            )

            duration_seconds = parse_duration_seconds(
                content_details.get("duration", "")
            )

            row["duration_seconds"] = duration_seconds
            row["format_candidate"] = classify_format(
                duration_seconds
            )

        # Videos absent from the API response may be unavailable
        # or inaccessible. Do not invent their statistics.
        missing_ids = set(batch) - returned_ids

        if missing_ids:
            print(
                "Warning: statistics unavailable for "
                f"{len(missing_ids)} video(s) in this batch."
            )

    # Step 3: Write the research CSV.
    # The scorer reads this file separately and does not modify it.
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

            output_row["matched_queries"] = "; ".join(
                sorted(row["matched_queries"])
            )

            writer.writerow(output_row)

    print(
        "Research complete. "
        f"Videos collected: {len(collected)}"
    )
    print(f"CSV saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
