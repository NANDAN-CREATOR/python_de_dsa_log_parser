"""
log_parser/indexer.py
=====================
LogIndexer — indexes log lines into a Trie for fast prefix search.

This is the "search engine" layer on top of the raw Trie data structure.

What it does
------------
1. Takes a list of log lines (strings)
2. Extracts the "key" from each line (e.g. the log level + category prefix)
3. Inserts each key + line_id into the Trie
4. Provides fast search(prefix) → matching log lines

Log line format expected
------------------------
    2024-01-15 09:23:45 ERROR.database.connection Failed to connect to DB
    2024-01-15 09:23:46 WARN.memory.heap         Heap usage at 85%
    2024-01-15 09:23:47 INFO.api.request         GET /api/users 200 OK
    2024-01-15 09:23:48 ERROR.database.timeout   Query timeout after 30s

The "key" extracted from each line is the log level + category:
    ERROR.database.connection
    WARN.memory.heap
    INFO.api.request
    ERROR.database.timeout

Searching for "ERROR.database" returns lines 1 and 4.
Searching for "ERROR"          returns lines 1 and 4.
Searching for "WARN"           returns line 2.

Elasticsearch connection
------------------------
This is conceptually identical to how Elasticsearch builds an inverted index:
  - ES tokenises each document field into terms
  - For each term, it records which document IDs contain it
  - A search looks up the term and returns the document IDs

The Trie adds prefix awareness:
  - Instead of exact term match, we can match any PREFIX
  - "ERROR.db" matches "ERROR.database.connection", "ERROR.database.timeout"
  - Elasticsearch does this with prefix queries backed by an FST
    (Finite State Transducer — a compressed Trie)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from .trie import Trie


# ─────────────────────────────────────────────────────────────────────────────
# Index stats
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IndexStats:
    """Metadata about a built index."""
    total_lines:  int   = 0
    indexed_keys: int   = 0
    trie_nodes:   int   = 0
    build_secs:   float = 0.0


@dataclass
class SearchResult:
    """Result of a search operation."""
    prefix:        str
    matching_lines: List[str]
    match_count:   int       = 0
    search_secs:   float     = 0.0

    def __post_init__(self):
        self.match_count = len(self.matching_lines)


# ─────────────────────────────────────────────────────────────────────────────
# LogIndexer
# ─────────────────────────────────────────────────────────────────────────────

class LogIndexer:
    """
    Indexes log lines into a Trie for fast prefix search.

    Parameters
    ----------
    key_extractor : callable that takes a log line string and returns the
                    key to index it under. Default: extract log level + category
                    (e.g. "ERROR.database.connection" from a standard log line)

    Example
    -------
    >>> indexer = LogIndexer()
    >>> indexer.build(log_lines)
    >>> result = indexer.search("ERROR.database")
    >>> print(result.match_count)
    1523
    >>> for line in result.matching_lines[:5]:
    ...     print(line)
    """

    # Default log pattern:
    # 2024-01-15 09:23:45 ERROR.database.connection  message...
    #                     ^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                     This is the key we extract
    _KEY_PATTERN = re.compile(
        r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[.\d]*\s+(\S+)"
    )

    def __init__(self, key_extractor=None):
        self._trie:      Trie            = Trie()
        self._lines:     List[str]       = []
        self._stats:     Optional[IndexStats] = None
        self._extractor  = key_extractor or self._default_key_extractor

    # ── Build ─────────────────────────────────────────────────────────────────

    def build(self, log_lines: List[str]) -> IndexStats:
        """
        Index all log lines into the Trie.

        For each line:
          1. Extract the key using key_extractor
          2. Insert (key, line_id) into the Trie
          3. All prefixes of the key now map to this line_id

        Time:  O(N × L) where N = lines, L = avg key length
        Space: O(N × L) for the Trie nodes

        Returns IndexStats with build time and node count.
        """
        self._trie  = Trie()
        self._lines = log_lines
        t_start     = time.perf_counter()
        indexed     = 0

        for line_id, line in enumerate(log_lines):
            key = self._extractor(line)
            if key:
                self._trie.insert(key, line_id)
                indexed += 1

        build_secs = time.perf_counter() - t_start

        self._stats = IndexStats(
            total_lines  = len(log_lines),
            indexed_keys = indexed,
            trie_nodes   = self._trie.count_nodes(),
            build_secs   = build_secs,
        )
        return self._stats

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, prefix: str) -> SearchResult:
        """
        Find all log lines whose key starts with prefix.

        Time: O(P + K) where P = prefix length, K = result count
        (P to walk the trie, K to retrieve matching lines)

        Compare to naive scan: O(N × M) where N = total lines, M = line length
        """
        t_start   = time.perf_counter()
        ids       = self._trie.search(prefix)
        lines_out = [self._lines[i] for i in sorted(ids) if i < len(self._lines)]
        secs      = time.perf_counter() - t_start

        return SearchResult(
            prefix         = prefix,
            matching_lines = lines_out,
            search_secs    = secs,
        )

    def search_naive(self, prefix: str) -> SearchResult:
        """
        Naive string scan — O(N × M) — for benchmarking comparison.
        Scans every single log line looking for the prefix anywhere in the line.
        This is what you'd do WITHOUT an index.
        """
        t_start   = time.perf_counter()
        key_ptn   = re.compile(
            r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[.\d]*\s+" + re.escape(prefix)
        )
        lines_out = [line for line in self._lines if key_ptn.match(line)]
        secs      = time.perf_counter() - t_start

        return SearchResult(
            prefix         = prefix,
            matching_lines = lines_out,
            search_secs    = secs,
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def stats(self) -> Optional[IndexStats]:
        return self._stats

    @property
    def trie(self) -> Trie:
        return self._trie

    def print_stats(self) -> None:
        if not self._stats:
            print("Index not built yet — call build() first")
            return
        s = self._stats
        print(f"\n  Index Stats")
        print(f"  {'─' * 38}")
        print(f"  Total lines   : {s.total_lines:>10,}")
        print(f"  Indexed keys  : {s.indexed_keys:>10,}")
        print(f"  Trie nodes    : {s.trie_nodes:>10,}")
        print(f"  Build time    : {s.build_secs:>10.3f}s")
        print()

    # ── Private ───────────────────────────────────────────────────────────────

    @classmethod
    def _default_key_extractor(cls, line: str) -> Optional[str]:
        """
        Extract the log key from a standard log line.
        Returns the level.category part, e.g. "ERROR.database.connection"
        Returns None if the line doesn't match the expected format.
        """
        m = cls._KEY_PATTERN.match(line)
        return m.group(1) if m else None
