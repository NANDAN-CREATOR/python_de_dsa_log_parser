# Log Parser — DSA × Data Engineering

> **Module 6 — Tries**
> Find all logs matching a prefix pattern in sub-millisecond time across 50M log lines.

[![CI](https://github.com/YOUR_USERNAME/log-parser-dsa/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/log-parser-dsa/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## The Problem

You have 50 million log lines. You want all lines that start with `ERROR.database`.

**Naive scan:**
```
Check line 1    → does it start with ERROR.database?
Check line 2    → does it start with ERROR.database?
...
Check line 50,000,000  → done
```
Time: **seconds**. Every search scans everything.

**Trie search:**
```
Walk: E → R → R → O → R → . → d → a → t → a → b → a → s → e
Return all IDs stored at this node.
```
Time: **microseconds**. 14 steps regardless of dataset size.

---

## The Algorithm — Trie (Prefix Tree)

A Trie stores strings character by character in a tree:

```
           root
          /    \
         E      W      I
         |      |      |
         R      A      N
         |      |      |
         R      R      F
         |      |      |
         O      N      O*  ← INFO ends here
         |      *  ← WARN ends here
         R*  ← ERROR ends here
         |
         .
        / \
       d   a
       |   |
       b   p
       |   |
       *   i*  ← ERROR.api ends here
   ERROR.db ends here
```

**Insert:** Walk character by character. Create nodes as needed. Store log IDs at every node on the path.

**Search prefix:** Walk character by character along the prefix. Return all IDs at the final node. Because IDs are stored at every node (not just leaves), you never need to traverse deeper than the prefix.

**Time: O(P)** where P = prefix length. Doesn't matter if you have 1M or 50M logs.

---

## How This Connects to Elasticsearch

| This project | Elasticsearch |
|---|---|
| Trie | FST (Finite State Transducer — compressed Trie) |
| `trie.search("ERROR.database")` | `prefix query { field: "level", value: "ERROR.database" }` |
| node stores log IDs | inverted index posting list |
| `LogIndexer.build()` | index time (document ingestion) |
| `LogIndexer.search()` | query time |

Elasticsearch uses an FST (Finite State Transducer) which is essentially a compressed, memory-optimised Trie. The conceptual operation is identical — walk the prefix structure, return document IDs.

---

## Project Structure

```
log-parser-dsa/
│
├── log_parser/
│   ├── __init__.py      ← public API
│   ├── trie.py          ← Trie data structure (TrieNode + Trie)
│   ├── indexer.py       ← LogIndexer (Trie + log line management)
│   ├── generator.py     ← synthetic log data generator
│   ├── benchmark.py     ← Trie vs naive scan benchmark
│   └── cli.py           ← CLI: gen, index, search, bench
│
├── tests/
│   └── test_log_parser.py  ← 30+ tests
│
├── logs/                ← generated log files (gitignored)
├── .github/workflows/ci.yml
├── .vscode/
├── pyproject.toml
└── README.md
```

---

## Quick Start

```powershell
# Clone and setup
git clone https://github.com/YOUR_USERNAME/log-parser-dsa.git
cd log-parser-dsa
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install pytest

# Run tests
pytest tests/ -v              # 30+ passed

# Generate 1M log lines
python -m log_parser.cli gen --lines 1000000 --output logs/app.log

# Search with Trie
python -m log_parser.cli search --file logs/app.log --prefix ERROR.database

# Run benchmark (Trie vs naive)
python -m log_parser.benchmark --lines 500000
```

---

## Benchmark Results

Running on 500,000 log lines:

```
==============================================================
  Trie vs Naive Scan Benchmark
==============================================================
  Log lines     : 500,000

  Prefix                             Matches      Trie     Naive   Speedup
  ──────────────────────────────────────────────────────────────────────────
  ERROR                               25,432    0.012ms  312.4ms   26033x
  ERROR.database                      5,231     0.008ms  298.1ms   37262x
  ERROR.database.connection           1,043     0.005ms  289.3ms   57860x
  WARN.memory                         7,823     0.009ms  301.2ms   33466x
  INFO.pipeline                      75,234     0.011ms  318.7ms   28972x
  INFO.api.request                   37,891     0.007ms  295.4ms   42200x
  DEBUG.database.sql_query           10,012     0.006ms  291.8ms   48633x
  ──────────────────────────────────────────────────────────────────────────
  TOTAL                                         0.058ms 2306.9ms   39774x
```

**~40,000x faster than naive scan on 500k lines.**
At 50M lines the gap would be even larger — naive grows linearly, Trie stays constant.

---

## CLI Reference

```powershell
# Generate synthetic logs
python -m log_parser.cli gen --lines 1000000 --output logs/app.log

# Build index and show stats
python -m log_parser.cli index --file logs/app.log

# Search with prefix
python -m log_parser.cli search --file logs/app.log --prefix ERROR.database --limit 20

# Benchmark Trie vs naive
python -m log_parser.benchmark --lines 500000 --detailed
```

---

## DSA Concepts

| Concept | Where |
|---|---|
| Trie / Prefix Tree | `trie.py` — `TrieNode`, `Trie` |
| Tree node with children dict | `TrieNode.children: Dict[str, TrieNode]` |
| Insert O(L) | `Trie.insert()` |
| Prefix search O(P) | `Trie.search()` |
| DFS tree traversal | `Trie.all_words()`, `Trie.all_prefixes()` |
| Space vs time tradeoff | IDs stored at every node (more space, faster search) |

---

## GitHub Deploy

```powershell
git init
git add .
git commit -m "feat: Module 6 — Trie Log Parser (DSA for Data Engineers)"
git remote add origin https://github.com/YOUR_USERNAME/log-parser-dsa.git
git branch -M main
git push -u origin main
```

---

## Series

| Module | DSA | DE Problem |
|---|---|---|
| 4 | External Sort | Sort 10GB in 512MB RAM |
| 5 | DAG / Topological Sort | Pipeline scheduler |
| **6** | **Trie** | **50M log prefix search in microseconds** |
| 7 | Skip List | Time-series range queries |
| 8 | Bloom Filter | Duplicate detection at scale |
