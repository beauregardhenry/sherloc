"""Add new apps from the stalkerware-indicators repository to app-flags.csv.

Run from anywhere. Expects the repository checked out at
`sherloc/stalkerware-indicators` (the workflow does that). Records the source
and date in `static_data/app-flags-source.json`, which the app shows.
"""

import os
import sys

# set current path to root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.getcwd())

import config  # noqa: E402
import indicators  # noqa: E402


def main() -> int:
    if not os.path.exists(config.IOC_FILE):
        print("IOC repo not initialized properly")
        return 1
    if not os.path.exists(config.APP_FLAGS_FILE):
        print("app-flags.csv not found")
        return 1
    try:
        added = indicators.update_list(
            config.IOC_FILE, config.APP_FLAGS_FILE, config.IOC_PATH, config.IOC_SOURCE_FILE
        )
    except Exception as e:  # yaml, csv and file errors
        print("Could not update the app list: {}".format(type(e).__name__))
        return 1
    print("\nFound and added " + str(added) + " new apps!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
