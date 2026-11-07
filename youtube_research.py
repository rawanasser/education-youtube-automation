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
    if not API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY is missing."
        )

    params = {
        **params,
        "key": API_KEY,
    }

    url = (
        f"{API_BASE}/{endpoint}?"
        f"{urllib.parse.urlencode(params)}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json"
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except Exception as exc:
        raise RuntimeError(
            f"YouTube API request failed "
            f"({endpoint}): {exc}"
        ) from None


def iso_utc(value):
    return value.isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def add_search_results(
    collected,
    query,
    search_pass,
    params,
):
    print(
        f"[{search_pass}] Researching: {query}"
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
            "id",
            {}
        ).get("videoId")

        snippet = item.get(
            "snippet",
            {}
        )

        if not video_id:
            continue

        if video_id not in collected:
            collected[video_id] = {
                "video_id": video_id,
                "title": snippet.get(
                    "title",
                    "",
                ),
                "channel_title": snippet.get(
                    "channelTitle",
                    "",
                ),
                "published_at": snippet.get(
                    "publishedAt",
                    "",
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
                    "description",
                    "",
                ),
                "research_date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            added += 1

        collected[video_id][
            "matched_queries"
        ].add(query)

        collected[video_id][
            "discovery_sources"
        ].add(query)

        collected[video_id][
            "search_passes"
        ].add(search_pass)

    print(
        f"  Results returned: {len(items)}; "
        f"new unique videos: {added}"
    )


def main():
    if not API_KEY:
        print(
            "ERROR: YOUTUBE_API_KEY is missing."
        )
        sys.exit(1)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    collected = {}

    now = datetime.now(timezone.utc)

    # ---------------------------------------------------------
    # PASS 1: Historical discovery
    #
    # Purpose:
    # Find established videos and long-term winners.
    # ---------------------------------------------------------

    for query in QUERIES:
        add_search_results(
            collected,
            query,
            "historical",
            {
                "order": "relevance",
            },
        )

    # ---------------------------------------------------------
    # PASS 2: Recent 8-30 day discovery
    #
    # Purpose:
    # Measure early traction while avoiding videos that
    # are only a few hours or days old.
    # ---------------------------------------------------------

    recent_8_start = now - timedelta(
        days=30
    )

    recent_8_end = now - timedelta(
        days=8
    )

    published_after_8_30 = iso_utc(
        recent_8_start
    )

    published_before_8_30 = iso_utc(
        recent_8_end
    )

    for query in QUERIES:
        add_search_results(
            collected,
            query,
            "recent_8_30",
            {
                "order": "relevance",
                "publishedAfter": published_after_8_30,
                "publishedBefore": published_before_8_30,
            },
        )

    # ---------------------------------------------------------
    # PASS 3: Recent 31-90 day discovery
    #
    # Purpose:
    # Measure more established recent performance.
    # ---------------------------------------------------------

    recent_31_start = now - timedelta(
        days=90
    )

    recent_31_end = now - timedelta(
        days=31
    )

    published_after_31_90 = iso_utc(
        recent_31_start
    )

    published_before_31_90 = iso_utc(
        recent_31_end
    )

    for query in QUERIES:
        add_search_results(
            collected,
            query,
            "recent_31_90",
            {
                "order": "relevance",
                "publishedAfter": published_after_31_90,
                "publishedBefore": published_before_31_90,
            },
        )

    video_ids = list(
        collected.keys()
    )

    print(
        f"\nUnique videos collected: "
        f"{len(video_ids)}"
    )

    # ---------------------------------------------------------
    # Fetch statistics and durations
    # ---------------------------------------------------------

    for start in range(
        0,
        len(video_ids),
        50,
    ):
        batch = video_ids[
            start:start + 50
        ]

        result = api_get(
            "videos",
            {
                "part": (
                    "statistics,"
                    "contentDetails"
                ),
                "id": ",".join(batch),
            },
        )

        returned_ids = set()

        for item in result.get(
            "items",
            [],
        ):
            video_id = item.get(
                "id"
            )

            returned_ids.add(
                video_id
            )

            row = collected.get(
                video_id
            )

            if row is None:
                continue

            statistics = item.get(
                "statistics",
                {}
            )

            details = item.get(
                "contentDetails",
                {}
            )

            row["views"] = statistics.get(
                "viewCount",
                ""
            )

            row["likes"] = statistics.get(
                "likeCount",
                ""
            )

            row["comments"] = statistics.get(
                "commentCount",
                ""
            )

            duration = parse_duration_seconds(
                details.get(
                    "duration",
                    "",
                )
            )

            row["duration_seconds"] = duration

            row["format_candidate"] = (
                classify_format(
                    duration
                )
            )

        missing_ids = (
            set(batch) - returned_ids
        )

        if missing_ids:
            print(
                f"Warning: "
                f"{len(missing_ids)} videos "
                "had unavailable statistics."
            )

    # ---------------------------------------------------------
    # Write CSV
    # ---------------------------------------------------------

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
                    sorted(
                        row[field]
                    )
                )

            writer.writerow(
                output_row
            )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    pass_counts = {
        "historical": 0,
        "recent_8_30": 0,
        "recent_31_90": 0,
    }

    for row in collected.values():
        for search_pass in pass_counts:
            if search_pass in row[
                "search_passes"
            ]:
                pass_counts[
                    search_pass
                ] += 1

    print("\nResearch complete.")
    print(
        f"Unique videos: "
        f"{len(collected)}"
    )

    print(
        f"Historical discoveries: "
        f"{pass_counts['historical']}"
    )

    print(
        f"Recent 8-30 day discoveries: "
        f"{pass_counts['recent_8_30']}"
    )

    print(
        f"Recent 31-90 day discoveries: "
        f"{pass_counts['recent_31_90']}"
    )

    both_recent_count = sum(
        (
            "recent_8_30" in row["search_passes"]
            and
            "recent_31_90" in row["search_passes"]
        )
        for row in collected.values()
    )

    print(
        f"Found in both recent windows: "
        f"{both_recent_count}"
    )

    print(
        f"CSV saved to: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
