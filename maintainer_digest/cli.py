"""Command-line entry point."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .github import GitHubClient, GitHubError, iso, repository, timestamp
from .report import analyze, markdown


def positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def write(path, content):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("Snapshot requires schema_version: 1")
    for field in ("collected_at", "since", "until"):
        timestamp(snapshot[field])
    if not isinstance(snapshot["repositories"], list) or not snapshot["repositories"]:
        raise ValueError("Snapshot requires a non-empty repositories list")
    if "notice" in snapshot and not isinstance(snapshot["notice"], str):
        raise ValueError("Snapshot notice must be a string")
    for data in snapshot["repositories"]:
        repository(data["repository"])
        for field in ("issues", "pulls", "open_issues", "open_pulls", "releases"):
            if not isinstance(data[field], list) or not all(isinstance(x, dict) for x in data[field]):
                raise ValueError("Invalid snapshot list: " + field)
        if not isinstance(data.get("warnings", []), list) or not all(isinstance(w, str) for w in data.get("warnings", [])):
            raise ValueError("Invalid snapshot warnings")
    return snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only GitHub maintenance reports. No LLM required.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--repo", action="append", help="owner/name or GitHub URL; repeat for multiple repositories")
    parser.add_argument("--input", help="Replay a JSON snapshot offline; uses its recorded time window")
    period = parser.add_mutually_exclusive_group()
    period.add_argument("--days", type=positive, help="Window length (default: 7 days)")
    period.add_argument("--since", help="Inclusive start, ISO 8601 or YYYY-MM-DD; naive dates use UTC")
    parser.add_argument("--until", help="Exclusive end, ISO 8601 or YYYY-MM-DD (default: now in UTC)")
    parser.add_argument("--lang", choices=("en", "zh"), default="en")
    parser.add_argument("--stale-days", type=positive, default=30)
    parser.add_argument("--max-pages", type=positive, default=10, help="Maximum pages per endpoint, 100 items per page")
    parser.add_argument("--limit", type=positive, default=20, help="Visible items per section; counts remain unabridged")
    parser.add_argument("--exclude-bots", action="store_true", help="Exclude records whose author is a bot")
    parser.add_argument("--output", help="Markdown destination (default: stdout)")
    parser.add_argument("--json-output", help="Write machine-readable metrics and sections")
    parser.add_argument("--save-data", help="Save collected API data for offline replay (may contain private data)")
    parser.add_argument("--strict", action="store_true", help="Exit 2 after writing a report if collection is incomplete")
    args = parser.parse_args(argv)
    if args.input and (args.repo or args.days or args.since or args.until):
        parser.error("--input cannot be combined with --repo, --days, --since or --until")
    if not args.input and not args.repo:
        parser.error("provide --repo or --input")
    destinations = [Path(x).resolve() for x in (args.output, args.json_output, args.save_data) if x]
    if len(set(destinations)) != len(destinations):
        parser.error("output destinations must be different files")
    if args.input and Path(args.input).resolve() in destinations:
        parser.error("output destinations must not overwrite the input snapshot")
    try:
        if args.input:
            snapshot = validate_snapshot(json.loads(Path(args.input).read_text(encoding="utf-8")))
            since, until = timestamp(snapshot["since"]), timestamp(snapshot["until"])
        else:
            until = timestamp(args.until) if args.until else datetime.now(timezone.utc).replace(microsecond=0)
            since = timestamp(args.since) if args.since else until - timedelta(days=args.days or 7)
            if since >= until:
                raise ValueError("--since must precede --until")
            repos = list(dict.fromkeys(repository(x) for x in args.repo))
            client = GitHubClient(os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"), max_pages=args.max_pages)
            collected = [client.collect(repo, since) for repo in repos]
            snapshot = {"schema_version": 1, "since": iso(since), "until": iso(until),
                        "collected_at": iso(datetime.now(timezone.utc)), "repositories": collected}
        if since >= until:
            raise ValueError("Snapshot start must precede end")
        reports = [analyze(data, since, until, args.stale_days, args.exclude_bots) for data in snapshot["repositories"]]
        output = markdown(reports, snapshot["collected_at"], args.lang, args.limit, snapshot.get("notice"))
        if args.output:
            write(args.output, output)
        else:
            sys.stdout.write(output)
        if args.json_output:
            write(args.json_output, json.dumps({"schema_version": 1, "collected_at": snapshot["collected_at"],
                                                "reports": reports}, ensure_ascii=False, indent=2) + "\n")
        if args.save_data:
            write(args.save_data, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        warnings = [warning for report in reports for warning in report["warnings"]]
        for warning in warnings:
            print("Warning: " + warning, file=sys.stderr)
        return 2 if warnings and args.strict else 0
    except (GitHubError, ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
        # Avoid dumping request objects or credentials in stack traces.
        message = str(exc)
        for key in ("GH_TOKEN", "GITHUB_TOKEN"):
            if os.getenv(key):
                message = message.replace(os.environ[key], "[REDACTED]")
        print("Error: " + message, file=sys.stderr)
        return 1
