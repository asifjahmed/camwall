"""camwall's detector, run by camwall when alerts are on (with the Python that has its models' libraries: torch,
open_clip_torch, ultralytics, pillow).

    python -m detector --port 8780          watch the cameras with alerts
    python -m detector --test-alert         make a test alert (sound, voice, notification)
"""

import argparse
import sys

from . import notify


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8780, help="camwall's port")
    parser.add_argument("--test-alert", action="store_true")
    args = parser.parse_args()
    if args.test_alert:
        notify.announce("Police at a test camera. This is a test.")
        return
    from . import watch  # (loads torch: slow)
    watch.run(args.port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
