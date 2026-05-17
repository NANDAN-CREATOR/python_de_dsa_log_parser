"""
log_parser/trie.py
==================
Trie (Prefix Tree) — built from scratch.

What is a Trie?
---------------
A Trie is a tree where each NODE represents one CHARACTER.
Walking from root to a leaf spells out a complete word/string.

Example — inserting "ERROR", "WARN", "ERROR.DB":

        root
        /  \\
       E    W
       |    |
       R    A
       |    |
       R    R
       |    |
       O    N
       |    |
       R*   *        ← * means "a complete word ends here"
       |
       .
       |
       D
       |
       B*

Why is this useful for log search?
-----------------------------------
Normal search: scan all 50M log lines one by one → O(N × M) where M = log line length
Trie search:   walk the prefix path → O(P) where P = prefix length (e.g. 5 chars)

For 50M logs with prefix "ERROR.DB" (8 chars):
  Normal: check all 50M lines  → slow
  Trie:   walk 8 nodes → instantly find all matching log IDs → fast

How Elasticsearch does it
--------------------------
Elasticsearch uses an "inverted index" — the same core idea:
  Instead of "for each document, does it contain this term?"
  It builds "for each term, which documents contain it?"

A Trie is a prefix-aware inverted index — instead of exact terms
it supports prefix lookups. Elasticsearch's prefix queries use
a similar structure internally (FST — Finite State Transducer).

DSA concepts used
-----------------
- Trie node (tree node with 256 children — one per ASCII char)
- Insert: O(L) where L = string length
- Search: O(P) where P = prefix length
- DFS traversal to collect all strings under a prefix
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Set


# ─────────────────────────────────────────────────────────────────────────────
# Trie Node
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TrieNode:
    """
    A single node in the Trie.

    children    : map from character → child TrieNode
    is_end      : True if a complete string ends at this node
    log_ids     : set of log line IDs stored at this node
                  (every node on the path to a word stores the IDs
                   so prefix search is O(P) — just walk to the prefix node
                   and return all IDs stored there and below)
    """
    children: Dict[str, "TrieNode"] = field(default_factory=dict)
    is_end:   bool                  = False
    log_ids:  Set[int]              = field(default_factory=set)


# ─────────────────────────────────────────────────────────────────────────────
# Trie
# ─────────────────────────────────────────────────────────────────────────────

class Trie:
    """
    Prefix tree for fast string prefix lookups.

    Supports:
      - insert(word, log_id)  — add a string with an associated ID
      - search(prefix)        — return all log IDs whose key starts with prefix
      - starts_with(prefix)   — return True/False if any key has this prefix
      - count_words()         — total number of inserted strings
      - all_words()           — iterate over every inserted string

    Example
    -------
    >>> t = Trie()
    >>> t.insert("ERROR.database.connection", log_id=1)
    >>> t.insert("ERROR.database.timeout",    log_id=2)
    >>> t.insert("WARN.memory",               log_id=3)
    >>>
    >>> t.search("ERROR.database")
    {1, 2}
    >>>
    >>> t.search("WARN")
    {3}
    >>>
    >>> t.search("INFO")
    set()
    """

    def __init__(self) -> None:
        self._root       = TrieNode()
        self._word_count = 0

    # ── Insert ────────────────────────────────────────────────────────────────

    def insert(self, word: str, log_id: int) -> None:
        """
        Insert a string into the Trie and associate it with log_id.

        Every node along the path from root to end stores log_id.
        This means a prefix search at any depth immediately returns
        all IDs without needing to traverse deeper.

        Time: O(L) where L = len(word)
        Space: O(L) new nodes in worst case (if word shares no prefix)
        """
        node = self._root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
            node.log_ids.add(log_id)   # ← store ID at every level

        if not node.is_end:
            node.is_end = True
            self._word_count += 1

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, prefix: str) -> Set[int]:
        """
        Return all log IDs whose inserted key starts with prefix.

        Algorithm:
          1. Walk the trie character by character along the prefix
          2. If any character is missing → no matches
          3. If we reach the end of the prefix → return all IDs at that node

        Because we store IDs at every node (not just leaf nodes),
        we only need to walk P steps (P = prefix length).
        No subtree traversal needed.

        Empty prefix → returns all IDs in the entire trie.

        Time:  O(P)  where P = len(prefix)
        Space: O(1)  (returning reference to existing set)
        """
        if prefix == "":
            # Collect all IDs from entire trie via DFS
            all_ids: Set[int] = set()
            def _collect(node: TrieNode) -> None:
                all_ids.update(node.log_ids)
                for child in node.children.values():
                    _collect(child)
            _collect(self._root)
            return all_ids

        node = self._find_node(prefix)
        if node is None:
            return set()
        return set(node.log_ids)

    def starts_with(self, prefix: str) -> bool:
        """
        Return True if any inserted key starts with prefix.
        Time: O(P)
        """
        return self._find_node(prefix) is not None

    def search_with_lines(
        self,
        prefix:    str,
        log_lines: List[str],
    ) -> List[str]:
        """
        Return the actual log line strings (not just IDs) matching prefix.
        Combines Trie ID lookup with index-based line retrieval.

        Time: O(P + K) where K = number of matching lines
        """
        ids = self.search(prefix)
        return [log_lines[i] for i in sorted(ids) if i < len(log_lines)]

    # ── Utilities ─────────────────────────────────────────────────────────────

    def count_words(self) -> int:
        """Total number of unique strings inserted."""
        return self._word_count

    def count_nodes(self) -> int:
        """Total number of TrieNodes in the tree (for memory analysis)."""
        count = [0]

        def _walk(node: TrieNode) -> None:
            count[0] += 1
            for child in node.children.values():
                _walk(child)

        _walk(self._root)
        return count[0]

    def all_words(self) -> Iterator[str]:
        """Iterate over every inserted string in lexicographic order."""
        def _dfs(node: TrieNode, path: List[str]) -> Iterator[str]:
            if node.is_end:
                yield "".join(path)
            for char in sorted(node.children.keys()):
                path.append(char)
                yield from _dfs(node.children[char], path)
                path.pop()

        yield from _dfs(self._root, [])

    def all_prefixes(self, prefix: str) -> List[str]:
        """
        Return all inserted strings that start with the given prefix.
        Useful for autocomplete-style features.
        """
        node = self._find_node(prefix)
        if node is None:
            return []

        results = []

        def _dfs(n: TrieNode, path: List[str]) -> None:
            if n.is_end:
                results.append(prefix[:-len(path)] + "".join(path) if path else prefix)
            for char in sorted(n.children.keys()):
                path.append(char)
                _dfs(n.children[char], path)
                path.pop()

        # Walk from prefix node
        suffix_parts: List[str] = []

        def _collect(n: TrieNode, built: str) -> None:
            if n.is_end:
                results.append(built)
            for char in sorted(n.children.keys()):
                _collect(n.children[char], built + char)

        _collect(node, prefix)
        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_node(self, prefix: str) -> Optional[TrieNode]:
        """
        Walk the trie along prefix. Return the node at the end of the
        prefix path, or None if the prefix doesn't exist in the trie.
        """
        node = self._root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def __repr__(self) -> str:
        return f"Trie(words={self._word_count}, nodes={self.count_nodes()})"
