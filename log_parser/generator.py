"""
log_parser/generator.py
========================
Generate synthetic application log files for benchmarking.

Log format:
    2024-01-15 09:23:45.123 ERROR.database.connection  Failed to connect: timeout
    2024-01-15 09:23:45.456 WARN.memory.heap           Heap usage at 87%
    2024-01-15 09:23:45.789 INFO.api.request           GET /api/users 200 23ms

Usage:
    python -m log_parser.generator --lines 1000000 --output logs/app.log
"""

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List


# ── Log taxonomy ──────────────────────────────────────────────────────────────

LOG_TAXONOMY = {
    "ERROR": {
        "database":  ["connection", "timeout", "query_failed", "deadlock", "pool_exhausted"],
        "api":       ["bad_request", "unauthorized", "internal", "rate_limit"],
        "storage":   ["write_failed", "read_failed", "disk_full", "permission_denied"],
        "auth":      ["token_expired", "invalid_credentials", "session_timeout"],
        "pipeline":  ["task_failed", "checkpoint_error", "schema_mismatch"],
    },
    "WARN": {
        "memory":    ["heap", "gc_pressure", "swap_usage", "leak_detected"],
        "network":   ["latency_high", "packet_loss", "connection_slow", "retry"],
        "database":  ["slow_query", "index_missing", "connection_pool_low"],
        "pipeline":  ["late_arrival", "schema_drift", "watermark_delay"],
        "api":       ["deprecated_endpoint", "high_response_time", "rate_limit_approaching"],
    },
    "INFO": {
        "api":       ["request", "response", "health_check", "metrics"],
        "pipeline":  ["task_started", "task_complete", "batch_processed", "checkpoint_saved"],
        "database":  ["connection_established", "query_complete", "migration_applied"],
        "auth":      ["login", "logout", "token_issued", "session_created"],
        "scheduler": ["dag_started", "dag_complete", "task_queued", "worker_assigned"],
    },
    "DEBUG": {
        "api":       ["request_headers", "response_body", "middleware_chain"],
        "database":  ["sql_query", "bind_params", "execution_plan"],
        "pipeline":  ["offset_committed", "batch_size", "partition_assigned"],
        "memory":    ["allocation", "gc_run", "cache_hit", "cache_miss"],
    },
}

LOG_MESSAGES = {
    "ERROR.database.connection":    ["Failed to connect to database: timeout after 30s",
                                     "Connection refused: host=db-prod-01 port=5432",
                                     "Max retry attempts exceeded for database connection"],
    "ERROR.database.timeout":       ["Query execution timeout after 60s",
                                     "Statement timeout: SELECT * FROM fact_sales",
                                     "Lock wait timeout exceeded"],
    "ERROR.api.internal":           ["Unhandled exception in request handler",
                                     "Internal server error: NullPointerException",
                                     "Request processing failed: unexpected error"],
    "WARN.memory.heap":             ["Heap usage at 85% — GC pressure increasing",
                                     "JVM heap space running low: 87% used",
                                     "Memory warning: consider increasing heap size"],
    "WARN.pipeline.late_arrival":   ["Late data detected: 2h behind watermark",
                                     "Event time lag exceeding threshold: 45min",
                                     "Out-of-order records: reprocessing window"],
    "INFO.api.request":             ["GET /api/users 200 23ms",
                                     "POST /api/orders 201 45ms",
                                     "GET /api/dashboard 200 12ms"],
    "INFO.pipeline.task_complete":  ["Task extract_bronze completed: 1,234,567 rows",
                                     "Task transform_silver done in 45.2s",
                                     "Batch processed: 500,000 records written"],
    "DEBUG.database.sql_query":     ["SELECT customer_id, SUM(amount) FROM orders GROUP BY 1",
                                     "UPDATE fact_sales SET processed=true WHERE batch_id=42",
                                     "INSERT INTO bronze.events SELECT * FROM staging"],
}

_DEFAULT_MESSAGE = "Application event recorded"


def _random_message(level: str, category: str, subcategory: str, rng: random.Random) -> str:
    key = f"{level}.{category}.{subcategory}"
    msgs = LOG_MESSAGES.get(key)
    if msgs:
        return rng.choice(msgs)
    return _DEFAULT_MESSAGE


def generate_log_lines(
    num_lines: int,
    seed:      int = 42,
) -> List[str]:
    """
    Generate synthetic log lines in memory.
    Returns a list of strings.
    """
    rng       = random.Random(seed)
    lines     = []
    base_time = datetime(2024, 1, 15, 9, 0, 0)

    # Weight distribution — ERROR less frequent than INFO
    level_weights = {"ERROR": 5, "WARN": 15, "INFO": 60, "DEBUG": 20}
    levels        = list(level_weights.keys())
    weights       = list(level_weights.values())

    for i in range(num_lines):
        # Advance time slightly
        base_time += timedelta(milliseconds=rng.randint(1, 100))
        ts = base_time.strftime("%Y-%m-%d %H:%M:%S.") + f"{rng.randint(0,999):03d}"

        level    = rng.choices(levels, weights=weights, k=1)[0]
        cats     = LOG_TAXONOMY[level]
        category = rng.choice(list(cats.keys()))
        subcat   = rng.choice(cats[category])
        key      = f"{level}.{category}.{subcat}"
        message  = _random_message(level, category, subcat, rng)

        lines.append(f"{ts}  {key:<35}  {message}")

    return lines


def generate_log_file(
    output_path: str,
    num_lines:   int,
    seed:        int = 42,
) -> dict:
    """Write synthetic log lines to a file. Returns stats dict."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    t0    = time.perf_counter()
    lines = generate_log_lines(num_lines, seed)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    return {
        "lines":     num_lines,
        "file_size": os.path.getsize(output_path),
        "time_secs": time.perf_counter() - t0,
        "output":    output_path,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="log-generator",
        description="Generate synthetic application log files for benchmarking."
    )
    p.add_argument("--lines",  "-n", type=int, default=100_000)
    p.add_argument("--output", "-o", default="logs/app.log")
    p.add_argument("--seed",   "-s", type=int, default=42)
    p.add_argument("--size-report", action="store_true")
    args = p.parse_args(argv)

    if args.size_report:
        est = args.lines * 120
        print(f"\n  Estimated size : ~{est / 1_048_576:.0f} MB ({args.lines:,} lines)")

    print(f"Generating {args.lines:,} log lines → {args.output} ...")
    s = generate_log_file(args.output, args.lines, args.seed)
    print(f"\n  ✅ Done!")
    print(f"  Lines : {s['lines']:,}")
    print(f"  Size  : {s['file_size'] / 1_048_576:.1f} MB")
    print(f"  Time  : {s['time_secs']:.2f}s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
