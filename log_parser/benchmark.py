"""
log_parser/benchmark.py
========================
Benchmark: Trie-based search vs naive linear scan.

This is the main proof of concept — shows WHY a Trie is valuable
for log search at scale.

Run:
    python -m log_parser.benchmark --lines 500000
    python -m log_parser.benchmark --lines 1000000 --detailed
"""

import argparse
import sys
import time
from typing import List

from .generator import generate_log_lines
from .indexer import LogIndexer


def run_benchmark(
    num_lines: int = 500_000,
    prefixes:  List[str] = None,
    detailed:  bool = False,
    seed:      int = 42,
) -> None:
    """
    Run the full Trie vs naive benchmark.

    Generates num_lines synthetic log lines,
    builds a Trie index,
    then compares search speed for several prefixes.
    """

    if prefixes is None:
        prefixes = [
            "ERROR",
            "ERROR.database",
            "ERROR.database.connection",
            "WARN.memory",
            "INFO.pipeline",
            "INFO.api.request",
            "DEBUG.database.sql_query",
        ]

    print(f"\n{'=' * 62}")
    print(f"  Trie vs Naive Scan Benchmark")
    print(f"{'=' * 62}")
    print(f"  Log lines     : {num_lines:,}")
    print(f"  Prefixes      : {len(prefixes)}")
    print()

    # ── Step 1: Generate logs ─────────────────────────────────────────────────
    print("  Step 1 — Generating synthetic log lines...")
    t0    = time.perf_counter()
    lines = generate_log_lines(num_lines, seed=seed)
    print(f"  Generated {len(lines):,} lines in {time.perf_counter() - t0:.2f}s")
    print()

    # ── Step 2: Build Trie index ──────────────────────────────────────────────
    print("  Step 2 — Building Trie index...")
    indexer = LogIndexer()
    stats   = indexer.build(lines)
    print(f"  Index built in {stats.build_secs:.3f}s")
    print(f"  Trie nodes    : {stats.trie_nodes:,}")
    print(f"  Indexed keys  : {stats.indexed_keys:,}")
    print()

    # ── Step 3: Benchmark each prefix ─────────────────────────────────────────
    print(f"  Step 3 — Search comparison")
    print(f"  {'─' * 58}")
    print(f"  {'Prefix':<35} {'Matches':>8}  {'Trie':>10}  {'Naive':>10}  {'Speedup':>8}")
    print(f"  {'─' * 58}")

    total_trie_ms  = 0.0
    total_naive_ms = 0.0

    for prefix in prefixes:
        trie_result  = indexer.search(prefix)
        naive_result = indexer.search_naive(prefix)

        trie_ms  = trie_result.search_secs  * 1000
        naive_ms = naive_result.search_secs * 1000
        speedup  = naive_ms / trie_ms if trie_ms > 0 else float("inf")

        total_trie_ms  += trie_ms
        total_naive_ms += naive_ms

        # Verify results match
        trie_ids  = {i for i, l in enumerate(lines)
                     if l in set(trie_result.matching_lines)}
        match_icon = "✅" if trie_result.match_count == naive_result.match_count else "⚠️"

        print(
            f"  {prefix:<35} "
            f"{trie_result.match_count:>8,}  "
            f"{trie_ms:>8.3f}ms  "
            f"{naive_ms:>8.3f}ms  "
            f"{speedup:>6.1f}x  {match_icon}"
        )

        if detailed and trie_result.matching_lines:
            print(f"    Sample: {trie_result.matching_lines[0][:80]}")

    print(f"  {'─' * 58}")
    overall_speedup = total_naive_ms / total_trie_ms if total_trie_ms > 0 else float("inf")
    print(
        f"  {'TOTAL':<35} "
        f"{'':>8}  "
        f"{total_trie_ms:>8.3f}ms  "
        f"{total_naive_ms:>8.3f}ms  "
        f"{overall_speedup:>6.1f}x"
    )
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"  Summary")
    print(f"  {'─' * 38}")
    print(f"  Trie total search time  : {total_trie_ms:.2f}ms")
    print(f"  Naive total search time : {total_naive_ms:.2f}ms")
    print(f"  Overall speedup         : {overall_speedup:.1f}x faster with Trie")
    print()
    print(f"  Why?")
    print(f"  ─ Naive scan checks every line: O(N × M)")
    print(f"    N={num_lines:,} lines × M=~100 chars = {num_lines * 100:,} char comparisons")
    print(f"  ─ Trie search walks only prefix: O(P)")
    print(f"    P = prefix length (3-25 chars) = tiny constant work")
    print(f"  ─ At 50M lines the difference is seconds vs microseconds")
    print(f"{'=' * 62}\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="log-benchmark",
        description="Benchmark Trie-based log search vs naive linear scan."
    )
    p.add_argument("--lines",    "-n", type=int, default=500_000,
                   help="Number of log lines (default: 500,000)")
    p.add_argument("--detailed", "-d", action="store_true",
                   help="Show sample matching lines")
    p.add_argument("--seed",     "-s", type=int, default=42)
    args = p.parse_args(argv)

    run_benchmark(
        num_lines = args.lines,
        detailed  = args.detailed,
        seed      = args.seed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
