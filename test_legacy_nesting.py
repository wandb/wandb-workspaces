"""Reproduce the legacy filter nesting bug.

Each round-trip of load → modify → save adds a new AND nesting level
because filters_to_expr parenthesises non-root AND nodes, and when the
user appends " and <new>" to the string, expr_to_filters re-parses
the parenthesised group as a nested AND child.
"""

import json
import os
os.environ["WANDB_BASE_URL"] = "http://localhost:9001"

from wandb_workspaces import expr


def tree_summary(node, depth=0):
    """Return a compact string summary of a Filters tree."""
    indent = "  " * depth
    if node.filters:
        children = "\n".join(tree_summary(c, depth + 1) for c in node.filters)
        return f"{indent}{node.op} (children: {len(node.filters)})\n{children}"
    name = node.key.name if node.key else "?"
    return f"{indent}{name} {node.op} {node.value!r}"


def roundtrip(filters_tree, modification):
    """Simulate one SDK load → modify → save cycle.

    Returns the new Filters tree that would be saved to the backend.
    """
    s = expr.filters_v2_to_string(expr.filters_tree_to_v2(filters_tree))
    modified = s + modification
    new_tree = expr.expr_to_filters(modified)
    return new_tree, s, modified


# Start with a clean legacy workspace: OR → AND → [a, b]
backend = expr.Filters(op="OR", filters=[
    expr.Filters(op="AND", filters=[
        expr.Filters(
            op="=",
            key=expr.Key(section="run", name="displayName"),
            value="we-are-never-getting-back-together",
            disabled=False,
        ),
        expr.Filters(
            op="=",
            key=expr.Key(section="run", name="displayName"),
            value="love-story",
            disabled=False,
        ),
    ])
])

print("=" * 60)
print("  Starting state")
print("=" * 60)
print(tree_summary(backend))


def max_and_depth(node, depth=0):
    """Count the deepest AND nesting."""
    if node.op == "AND" and node.filters:
        return max(max_and_depth(c, depth + 1) for c in node.filters)
    return depth


for i in range(4):
    print(f"\n{'=' * 60}")
    print(f"  Round-trip {i + 1}: append ' and Config(\"lr\") == {i}'")
    print(f"{'=' * 60}")

    backend, original_str, modified_str = roundtrip(
        backend, f" and Config('lr') == {i}"
    )

    print(f"  Original string: {original_str!r}")
    print(f"  Modified string: {modified_str!r}")
    print()
    print(tree_summary(backend))

    depth = max_and_depth(backend)
    print(f"\n  AND nesting depth: {depth}")
    if depth > 1:
        print("  ^^^ BUG: nesting is growing!")
    else:
        print("  OK: flat structure maintained")
