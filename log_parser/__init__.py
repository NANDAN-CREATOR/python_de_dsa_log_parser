"""
log_parser
==========
Trie-based log pattern indexer.

Find all log lines matching a prefix pattern in sub-millisecond time,
regardless of how many millions of log lines exist.

DSA: Trie (prefix tree) — O(P) search vs O(N×M) naive scan
DE:  Conceptually identical to Elasticsearch's prefix query (backed by FST)

Quick start
-----------
    >>> from log_parser import Trie, LogIndexer
    >>> from log_parser.generator import generate_log_lines
    >>>
    >>> lines   = generate_log_lines(1_000_000)
    >>> indexer = LogIndexer()
    >>> indexer.build(lines)
    >>>
    >>> result = indexer.search("ERROR.database")
    >>> print(f"Found {result.match_count:,} matches in {result.search_secs*1000:.3f}ms")
"""

from .indexer import IndexStats, LogIndexer, SearchResult
from .trie import Trie, TrieNode

__all__    = ["Trie", "TrieNode", "LogIndexer", "IndexStats", "SearchResult"]
__version__ = "1.0.0"
__author__  = "Aman"
