
from datetime import datetime, timezone
import json
import os

def main():
    result = {
        "status": "success",
        "project": "education-youtube-automation",
        "message": "Cloud automation is working!",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner": os.getenv("GITHUB_ACTIONS", "local"),
    }

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
