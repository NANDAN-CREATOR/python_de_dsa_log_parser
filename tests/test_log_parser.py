"""
tests/test_log_parser.py
========================
Full test suite — Trie, LogIndexer, generator, CLI.
"""

import pytest
from log_parser import LogIndexer, SearchResult, Trie
from log_parser.cli import main as cli_main
from log_parser.generator import generate_log_lines


# ─────────────────────────────────────────────────────────────────────────────
# Trie — basic operations
# ─────────────────────────────────────────────────────────────────────────────

class TestTrieBasic:

    def test_insert_and_search_exact(self):
        t = Trie()
        t.insert("ERROR.database", log_id=1)
        assert 1 in t.search("ERROR.database")

    def test_prefix_search(self):
        t = Trie()
        t.insert("ERROR.database.connection", log_id=1)
        t.insert("ERROR.database.timeout",    log_id=2)
        t.insert("ERROR.api.internal",        log_id=3)

        result = t.search("ERROR.database")
        assert 1 in result
        assert 2 in result
        assert 3 not in result

    def test_short_prefix_matches_all(self):
        t = Trie()
        t.insert("ERROR.database", log_id=1)
        t.insert("ERROR.api",      log_id=2)
        t.insert("WARN.memory",    log_id=3)

        result = t.search("ERROR")
        assert 1 in result
        assert 2 in result
        assert 3 not in result

    def test_no_match_returns_empty_set(self):
        t = Trie()
        t.insert("ERROR.database", log_id=1)
        assert t.search("INFO") == set()

    def test_empty_prefix_matches_all(self):
        t = Trie()
        t.insert("ERROR", log_id=1)
        t.insert("WARN",  log_id=2)
        t.insert("INFO",  log_id=3)
        result = t.search("")
        assert {1, 2, 3}.issubset(result)

    def test_starts_with_true(self):
        t = Trie()
        t.insert("ERROR.database.connection", log_id=1)
        assert t.starts_with("ERROR") is True
        assert t.starts_with("ERROR.database") is True

    def test_starts_with_false(self):
        t = Trie()
        t.insert("ERROR.database", log_id=1)
        assert t.starts_with("INFO") is False

    def test_same_id_multiple_words(self):
        t = Trie()
        t.insert("ERROR.db", log_id=1)
        t.insert("ERROR.api", log_id=1)   # same ID
        result = t.search("ERROR")
        assert result == {1}

    def test_multiple_ids_same_prefix(self):
        t = Trie()
        for i in range(100):
            t.insert(f"ERROR.database.conn_{i}", log_id=i)
        result = t.search("ERROR.database")
        assert len(result) == 100

    def test_count_words(self):
        t = Trie()
        t.insert("ERROR", log_id=1)
        t.insert("WARN",  log_id=2)
        t.insert("INFO",  log_id=3)
        assert t.count_words() == 3

    def test_count_words_duplicate_insert(self):
        t = Trie()
        t.insert("ERROR", log_id=1)
        t.insert("ERROR", log_id=2)  # same word, different ID
        assert t.count_words() == 1  # word count stays 1

    def test_all_words(self):
        t = Trie()
        words = ["ERROR", "INFO", "WARN"]
        for i, w in enumerate(words):
            t.insert(w, log_id=i)
        assert sorted(t.all_words()) == sorted(words)

    def test_all_prefixes(self):
        t = Trie()
        t.insert("ERROR.db.connection", log_id=1)
        t.insert("ERROR.db.timeout",    log_id=2)
        t.insert("ERROR.api",           log_id=3)
        result = t.all_prefixes("ERROR.db")
        assert "ERROR.db.connection" in result
        assert "ERROR.db.timeout"    in result
        assert "ERROR.api"           not in result

    def test_count_nodes_grows_with_unique_chars(self):
        t = Trie()
        t.insert("ABC", log_id=1)
        nodes_after_abc = t.count_nodes()
        t.insert("ABD", log_id=2)  # shares "AB" prefix
        nodes_after_abd = t.count_nodes()
        # Only 1 new node added (D branch)
        assert nodes_after_abd == nodes_after_abc + 1

    def test_unicode_keys(self):
        t = Trie()
        t.insert("ERROR.数据库", log_id=1)
        assert 1 in t.search("ERROR.数据库")
        assert 1 in t.search("ERROR")


# ─────────────────────────────────────────────────────────────────────────────
# Trie — edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestTrieEdgeCases:

    def test_empty_trie_search(self):
        t = Trie()
        assert t.search("ERROR") == set()

    def test_single_char_key(self):
        t = Trie()
        t.insert("E", log_id=99)
        assert 99 in t.search("E")

    def test_prefix_longer_than_any_key(self):
        t = Trie()
        t.insert("ERR", log_id=1)
        # Search for a prefix longer than any inserted key
        assert t.search("ERROR.database.connection.pool") == set()

    def test_large_number_of_ids(self):
        t = Trie()
        for i in range(10_000):
            t.insert("ERROR.database", log_id=i)
        result = t.search("ERROR")
        assert len(result) == 10_000


# ─────────────────────────────────────────────────────────────────────────────
# LogIndexer
# ─────────────────────────────────────────────────────────────────────────────

class TestLogIndexer:

    def _make_lines(self):
        return [
            "2024-01-15 09:00:00.000  ERROR.database.connection  Connection failed",
            "2024-01-15 09:00:01.000  ERROR.database.timeout     Query timed out",
            "2024-01-15 09:00:02.000  WARN.memory.heap           Heap 85%",
            "2024-01-15 09:00:03.000  INFO.api.request           GET /api 200",
            "2024-01-15 09:00:04.000  DEBUG.database.sql_query   SELECT 1",
        ]

    def test_build_returns_stats(self):
        indexer = LogIndexer()
        stats   = indexer.build(self._make_lines())
        assert stats.total_lines  == 5
        assert stats.indexed_keys == 5
        assert stats.build_secs   >= 0

    def test_search_exact_level(self):
        indexer = LogIndexer()
        indexer.build(self._make_lines())
        result = indexer.search("ERROR")
        assert result.match_count == 2

    def test_search_level_category(self):
        indexer = LogIndexer()
        indexer.build(self._make_lines())
        result = indexer.search("ERROR.database")
        assert result.match_count == 2

    def test_search_full_key(self):
        indexer = LogIndexer()
        indexer.build(self._make_lines())
        result = indexer.search("ERROR.database.connection")
        assert result.match_count == 1

    def test_search_no_match(self):
        indexer = LogIndexer()
        indexer.build(self._make_lines())
        result = indexer.search("CRITICAL")
        assert result.match_count == 0
        assert result.matching_lines == []

    def test_search_returns_actual_lines(self):
        indexer = LogIndexer()
        lines   = self._make_lines()
        indexer.build(lines)
        result = indexer.search("WARN")
        assert len(result.matching_lines) == 1
        assert "Heap 85%" in result.matching_lines[0]

    def test_search_records_time(self):
        indexer = LogIndexer()
        indexer.build(self._make_lines())
        result = indexer.search("ERROR")
        assert result.search_secs >= 0

    def test_naive_search_matches_trie_results(self):
        indexer = LogIndexer()
        indexer.build(self._make_lines())
        trie_result  = indexer.search("ERROR.database")
        naive_result = indexer.search_naive("ERROR.database")
        assert trie_result.match_count == naive_result.match_count

    def test_malformed_lines_skipped(self):
        lines = [
            "not a valid log line",
            "also bad",
            "2024-01-15 09:00:00.000  ERROR.db  valid line",
        ]
        indexer = LogIndexer()
        stats   = indexer.build(lines)
        assert stats.indexed_keys == 1

    def test_large_dataset(self):
        lines   = generate_log_lines(10_000)
        indexer = LogIndexer()
        stats   = indexer.build(lines)
        assert stats.total_lines == 10_000
        result = indexer.search("ERROR")
        assert result.match_count > 0
        # Verify Trie and naive give same count
        naive = indexer.search_naive("ERROR")
        assert result.match_count == naive.match_count


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerator:

    def test_generates_correct_count(self):
        lines = generate_log_lines(1_000)
        assert len(lines) == 1_000

    def test_deterministic_with_same_seed(self):
        a = generate_log_lines(100, seed=1)
        b = generate_log_lines(100, seed=1)
        assert a == b

    def test_different_seeds_differ(self):
        a = generate_log_lines(100, seed=1)
        b = generate_log_lines(100, seed=2)
        assert a != b

    def test_lines_have_correct_format(self):
        import re
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}")
        lines   = generate_log_lines(100)
        for line in lines:
            assert pattern.match(line), f"Bad format: {line}"

    def test_all_levels_present(self):
        lines = generate_log_lines(10_000)
        text  = "\n".join(lines)
        for level in ["ERROR", "WARN", "INFO", "DEBUG"]:
            assert level in text


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

class TestCLI:

    def test_gen_command(self, tmp_path):
        out = str(tmp_path / "test.log")
        rc  = cli_main(["gen", "--lines", "1000", "--output", out])
        assert rc == 0
        assert (tmp_path / "test.log").exists()

    def test_index_command(self, tmp_path):
        # Generate then index
        out = str(tmp_path / "test.log")
        cli_main(["gen", "--lines", "1000", "--output", out])
        rc = cli_main(["index", "--file", out])
        assert rc == 0

    def test_search_command(self, tmp_path):
        out = str(tmp_path / "test.log")
        cli_main(["gen", "--lines", "1000", "--output", out])
        rc = cli_main(["search", "--file", out, "--prefix", "ERROR"])
        assert rc == 0

    def test_bench_command_small(self):
        rc = cli_main(["bench", "--lines", "5000"])
        assert rc == 0
