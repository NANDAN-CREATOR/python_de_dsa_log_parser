import os
from log_parser.trie import Trie, TrieNode

def build_trie_string(node: TrieNode, prefix: str = "", is_last: bool = True, depth: int = 0) -> str:
    """Build the Trie as an ASCII string."""
    lines = []
    
    if depth == 0:
        lines.append("root")
    
    children = sorted(node.children.items())
    for i, (char, child) in enumerate(children):
        is_last_child = (i == len(children) - 1)
        connector     = "└─" if is_last_child else "├─"
        ids_str       = f"  ids={sorted(child.log_ids)}" if child.log_ids else ""
        end_marker    = "*" if child.is_end else ""

        lines.append(f"{prefix}{connector} {char}{end_marker}{ids_str}")
        lines.append(
            build_trie_string(
                child,
                prefix  = prefix + ("   " if is_last_child else "│  "),
                is_last = is_last_child,
                depth   = depth + 1,
            )
        )

    return "\n".join(line for line in lines if line)


def save_trie(trie: Trie, output_path: str, label: str = "") -> None:
    """Save Trie visualisation to a text file."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    tree_str = build_trie_string(trie._root)

    content = f"""{'=' * 56}
TRIE STRUCTURE — {label}
{'=' * 56}

{tree_str}

{'─' * 56}
Summary
{'─' * 56}
  Total words  : {trie.count_words()}
  Total nodes  : {trie.count_nodes()}
{'=' * 56}
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Trie saved → {output_path}")
    print(f"   Words : {trie.count_words()}")
    print(f"   Nodes : {trie.count_nodes()}")


# ── Build Trie and save ───────────────────────────────────────────────────────

t = Trie()
t.insert("ERROR.database.connection", log_id=1)
t.insert("ERROR.database.timeout",    log_id=2)
t.insert("ERROR.api.internal",        log_id=3)
t.insert("WARN.memory.heap",          log_id=4)
t.insert("INFO.api.request",          log_id=5)

# Print to terminal
print(build_trie_string(t._root))

# Save to file
save_trie(t, output_path="output/trie_structure.txt", label="Sample Log Keys")