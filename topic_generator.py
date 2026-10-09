
import csv
from datetime import datetime, timezone
from pathlib import Path

TOPICS = [
    {
        "pillar": "How the World Works",
        "question": "How does GPS know where you are?",
        "title": "How GPS Knows Your Location",
        "hook": "Your phone can locate you without seeing a map. How?",
        "long": "Explain satellite signals, timing, and location calculation.",
        "short": "Explain GPS in three simple steps."
    },
    {
        "pillar": "How the World Works",
        "question": "How does the internet move information?",
        "title": "How the Internet Actually Works",
        "hook": "What happens after you tap a link?",
        "long": "Follow a request from a device to a web server and back.",
        "short": "Explain how a web page reaches your phone."
    },
    {
        "pillar": "Technology & AI",
        "question": "How does ChatGPT generate answers?",
        "title": "How ChatGPT Actually Works",
        "hook": "How can an AI produce an answer one word at a time?",
        "long": "Explain language models, tokens, training, and prediction.",
        "short": "Explain next-token prediction with a simple example."
    },
    {
        "pillar": "Technology & AI",
        "question": "How do recommendation systems choose videos?",
        "title": "How YouTube Recommends Videos",
        "hook": "Why do two people see different recommendations?",
        "long": "Explain signals, ranking, and personalized recommendations.",
        "short": "Explain one reason recommendations differ."
    },
    {
        "pillar": "Technology & AI",
        "question": "How does face recognition work?",
        "title": "How Phones Recognize Your Face",
        "hook": "How can a phone distinguish one face from another?",
        "long": "Explain facial features, matching, and system limitations.",
        "short": "Explain face matching with a simple diagram."
    },
    {
        "pillar": "Science & Human Understanding",
        "question": "Why is the sky blue?",
        "title": "Why the Sky Looks Blue",
        "hook": "Sunlight looks almost white, so why is the sky blue?",
        "long": "Explain sunlight and Rayleigh scattering.",
        "short": "Explain why air scatters blue light more strongly."
    },
    {
        "pillar": "Science & Human Understanding",
        "question": "Why do we dream?",
        "title": "What Science Knows About Dreams",
        "hook": "Scientists have clues about dreams, but not every answer.",
        "long": "Explore sleep research and leading explanations of dreaming.",
        "short": "Share one evidence-based fact about dreaming."
    },
    {
        "pillar": "Science & Human Understanding",
        "question": "Why do we experience time differently?",
        "title": "Why Time Sometimes Feels Faster",
        "hook": "Why can an hour feel short one day and long the next?",
        "long": "Explore attention, memory, and time perception.",
        "short": "Explain one factor that changes time perception."
    }
]


def main():
    today = datetime.now(timezone.utc).date()
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Rotate the starting point daily so the list changes order.
    start = today.toordinal() % len(TOPICS)
    selected = TOPICS[start:] + TOPICS[:start]

    filename = output_dir / f"topic_ideas_{today.isoformat()}.csv"

    with filename.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "pillar", "question", "title", "hook",
                "long_video_angle", "short_video_angle"
            ]
        )
        writer.writeheader()

        for topic in selected:
            writer.writerow({
                "pillar": topic["pillar"],
                "question": topic["question"],
                "title": topic["title"],
                "hook": topic["hook"],
                "long_video_angle": topic["long"],
                "short_video_angle": topic["short"]
            })

    print(f"Created {filename}")
    print(f"Topic ideas: {len(selected)}")
    print("Source: built-in topic seed list; not live trend research.")


if __name__ == "__main__":
    main()
