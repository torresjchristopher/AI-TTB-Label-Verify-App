import argparse
import json
import os
import sys

from labelscan.pipeline import scan
from labelscan.selftest import run_self_test


def build_parser():
    parser = argparse.ArgumentParser(
        prog="labelscan",
        description="Local ONNX OCR and alcohol-label field matching CLI.",
    )
    sub = parser.add_subparsers(dest="command")

    scan_parser = sub.add_parser("scan", help="Scan one image or a folder.")
    scan_parser.add_argument("input", help="Image file or folder of images.")
    scan_parser.add_argument("--manifest", help="Optional expected-values CSV.")
    scan_parser.add_argument("--output", default="labelscan-output",
                             help="Output directory (default: labelscan-output).")
    scan_parser.add_argument("--workers", type=int, default=2,
                             help="Concurrent OCR workers, 1-4 (default: 2).")
    scan_parser.add_argument("--recursive", action="store_true",
                             help="Include images in subfolders.")
    scan_parser.add_argument("--limit", type=int,
                             help="Process at most this many images.")
    scan_parser.add_argument("--aggressive", action="store_true",
                             help="Always run all crop/enhancement passes.")

    sub.add_parser("self-test", help="Generate and OCR a known synthetic label.")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2
    try:
        if args.command == "self-test":
            summary = run_self_test()
        else:
            summary = scan(
                args.input,
                args.manifest,
                args.output,
                args.workers,
                args.recursive,
                args.limit,
                args.aggressive,
            )
        print("")
        print(json.dumps(summary, indent=2))
        return 1 if summary.get("errors", 0) else 0
    except (ValueError, FileNotFoundError) as exc:
        print("Input error:", exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print("Fatal error: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
