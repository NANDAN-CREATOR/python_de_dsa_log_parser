"""
log_parser/cli.py
=================
Command-line interface.

Commands:
    index   — build a Trie index from a log file
    search  — search an indexed log file
    bench   — run Trie vs naive benchmark
    gen     — generate synthetic log data

Usage:
    python -m log_parser.cli gen   --lines 1000000 --output logs/app.log
    python -m log_parser.cli index --file logs/app.log
    python -m log_parser.cli search --file logs/app.log --prefix ERROR.database
    python -m log_parser.cli bench  --lines 500000
"""

import argparse
import sys
import time

from .benchmark import run_benchmark
from .generator import generate_log_file
from .indexer import LogIndexer


def cmd_gen(args) -> int:
    print(f"Generating {args.lines:,} log lines → {args.output} ...")
    s = generate_log_file(args.output, args.lines, args.seed)
    print(f"✅ Done! {s['lines']:,} lines, {s['file_size']/1_048_576:.1f} MB, {s['time_secs']:.2f}s")
    return 0


def cmd_index(args) -> int:
    print(f"Reading {args.file} ...")
    with open(args.file, encoding="utf-8") as fh:
        lines = [l.rstrip() for l in fh if l.strip()]

    print(f"Building Trie index over {len(lines):,} lines ...")
    indexer = LogIndexer()
    stats   = indexer.build(lines)
    print(f"\n✅ Index built!")
    indexer.print_stats()
    return 0


def cmd_search(args) -> int:
    print(f"Reading {args.file} ...")
    with open(args.file, encoding="utf-8") as fh:
        lines = [l.rstrip() for l in fh if l.strip()]

    print(f"Building index over {len(lines):,} lines ...")
    indexer = LogIndexer()
    indexer.build(lines)

    result = indexer.search(args.prefix)
    print(f"\n  Search: '{args.prefix}'")
    print(f"  Matches: {result.match_count:,}  ({result.search_secs*1000:.3f}ms)")
    print()

    limit = min(args.limit, result.match_count)
    for line in result.matching_lines[:limit]:
        print(f"  {line}")
    if result.match_count > limit:
        print(f"  ... and {result.match_count - limit:,} more")
    return 0


def cmd_bench(args) -> int:
    run_benchmark(num_lines=args.lines, detailed=args.detailed, seed=args.seed)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="log-parser",
        description="Trie-based log indexer and search engine."
    )
    sub = p.add_subparsers(dest="command")

    # gen
    g = sub.add_parser("gen", help="Generate synthetic log data")
    g.add_argument("--lines",  "-n", type=int, default=100_000)
    g.add_argument("--output", "-o", default="logs/app.log")
    g.add_argument("--seed",   "-s", type=int, default=42)

    # index
    i = sub.add_parser("index", help="Build Trie index from log file")
    i.add_argument("--file", "-f", required=True)

    # search
    s = sub.add_parser("search", help="Search a log file using Trie index")
    s.add_argument("--file",   "-f", required=True)
    s.add_argument("--prefix", "-p", required=True)
    s.add_argument("--limit",  "-l", type=int, default=10)

    # bench
    b = sub.add_parser("bench", help="Benchmark Trie vs naive scan")
    b.add_argument("--lines",    "-n", type=int, default=500_000)
    b.add_argument("--detailed", "-d", action="store_true")
    b.add_argument("--seed",     "-s", type=int, default=42)

    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    dispatch = {
        "gen":    cmd_gen,
        "index":  cmd_index,
        "search": cmd_search,
        "bench":  cmd_bench,
    }

    if args.command not in dispatch:
        _build_parser().print_help()
        return 0

    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
