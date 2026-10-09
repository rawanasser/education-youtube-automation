
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

# A small initial query set to conserve API quota.
QUERIES = [
    "how artificial intelligence works educational",
    "how the world works science explained",
    "technology explained for beginners",
]

API_BASE = "https://www.googleapis.com/youtube/v3"


def api_get(endpoint, params):
    params = {**params, "key": API_KEY}
    url = f"{API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # Do not print the request URL: it contains the API key.
        raise RuntimeError(
            f"YouTube API request failed ({endpoint}): {exc}"
        ) from None


def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_API_KEY environment variable is missing.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    collected = {}

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

            row = collected.setdefault(
                video_id,
                {
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "description": snippet.get("description", ""),
                    "matched_queries": set(),
                    "views": "",
                    "likes": "",
                    "comments": "",
                    "research_date_utc": datetime.now(
                        timezone.utc
                    ).isoformat(),
                },
            )
            row["matched_queries"].add(query)

    video_ids = list(collected.keys())

    # Fetch public statistics in batches of up to 50 video IDs.
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        stats = api_get(
            "videos",
            {
                "part": "statistics",
                "id": ",".join(batch),
            },
        )

        for item in stats.get("items", []):
            video_id = item["id"]
            statistics = item.get("statistics", {})
            row = collected.get(video_id)

            if row is not None:
                row["views"] = statistics.get("viewCount", "")
                row["likes"] = statistics.get("likeCount", "")
                row["comments"] = statistics.get("commentCount", "")

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
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for row in collected.values():
            row["matched_queries"] = "; ".join(
                sorted(row["matched_queries"])
            )
            writer.writerow(row)

    print(f"Research complete. Videos collected: {len(collected)}")
    print(f"CSV saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
