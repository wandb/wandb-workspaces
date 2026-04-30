"""Test: string filters with ANDs, ORs, and parenthesised groups.

Exercises the string → Filters tree → v2 dict pipeline locally (no server).
Shows how each expression is parsed and what v2 dict is produced, verifying
that groups only appear for explicit parentheses.

Run with:
    python test_string_filters.py
"""

import json
import textwrap

from wandb_workspaces.expr import expr_to_filters, filters_tree_to_v2, filters_v2_to_string


def banner(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def run_case(label, expr_str, expect_groups):
    """Parse a string filter, convert to v2, and print the result.

    Args:
        label: Short description of the test case.
        expr_str: The filter expression string.
        expect_groups: Whether we expect FilterV2Group items in the output.
    """
    banner(label)
    print(f"  Input string:  {expr_str}")

    tree = expr_to_filters(expr_str)
    roundtrip = filters_v2_to_string(filters_tree_to_v2(tree))
    print(f"  Round-trip:    {roundtrip}")

    v2 = filters_tree_to_v2(tree)
    filters_list = v2.get("filters", [])

    print(f"  v2 dict:")
    print(textwrap.indent(json.dumps(v2, indent=2), "    "))

    groups = [f for f in filters_list if "filters" in f]
    flat = [f for f in filters_list if "key" in f]
    connectors = [f.get("connector") for f in flat]

    print(f"\n  Flat items: {len(flat)}  |  Groups: {len(groups)}  |  Connectors: {connectors}")

    has_groups = len(groups) > 0
    status = "PASS" if has_groups == expect_groups else "FAIL"
    print(f"  Groups expected: {expect_groups}  |  Got: {has_groups}  →  {status}")

    if status == "FAIL":
        print("  *** UNEXPECTED RESULT ***")

    return status


# ─── Run all cases ────────────────────────────────────────────────────────────

results = []

results.append(run_case(
    "1. Simple AND: A and B",
    "Metric('Name') == 'folklore' and Metric('State') == 'finished'",
    expect_groups=False,
))

results.append(run_case(
    "2. Simple OR: A or B",
    "Metric('Name') == 'folklore' or Metric('Name') == 'evermore'",
    expect_groups=False,
))

results.append(run_case(
    "3. Mixed no parens: A or B and C  (AND binds tighter, no group needed)",
    "Metric('Name') == 'folklore' or Metric('Name') == 'evermore' and Metric('State') == 'finished'",
    expect_groups=False,
))

results.append(run_case(
    "4. Mixed no parens: A and B or C  (= (A and B) or C, no group needed)",
    "Metric('Name') == 'folklore' and Metric('State') == 'finished' or Metric('Name') == 'evermore'",
    expect_groups=False,
))

results.append(run_case(
    "5. Explicit parens: A and (B or C)  → group for (B or C)",
    "Metric('Name') == 'folklore' and (Metric('Name') == 'evermore' or Metric('State') == 'finished')",
    expect_groups=True,
))

results.append(run_case(
    "6. Explicit parens: A or B and (C or D)  → group for (C or D)",
    "Metric('Name') == 'folklore' or Metric('Name') == 'evermore' and (Metric('State') == 'finished' or Metric('Name') == 'exile')",
    expect_groups=True,
))

results.append(run_case(
    "7. Two groups: (A or B) and (C or D)  → two groups",
    "(Metric('Name') == 'folklore' or Metric('Name') == 'evermore') and (Metric('State') == 'finished' or Metric('Name') == 'exile')",
    expect_groups=True,
))

results.append(run_case(
    "8. All OR: A or B or C  (flat, no groups)",
    "Metric('Name') == 'folklore' or Metric('Name') == 'evermore' or Metric('State') == 'finished'",
    expect_groups=False,
))

results.append(run_case(
    "9. All AND: A and B and C  (flat, no groups)",
    "Metric('Name') == 'folklore' and Metric('Name') == 'evermore' and Metric('State') == 'finished'",
    expect_groups=False,
))

results.append(run_case(
    "10. Nested parens: (A and B) or (C and D)  → no groups (AND inside OR doesn't need grouping)",
    "(Metric('Name') == 'folklore' and Metric('State') == 'finished') or (Metric('Name') == 'evermore' and Metric('State') == 'crashed')",
    expect_groups=False,
))

results.append(run_case(
    "11. Deep nesting: A or (B and (C or D))  → one group for (C or D)",
    "Metric('Name') == 'folklore' or (Metric('Name') == 'evermore' and (Metric('State') == 'finished' or Metric('Name') == 'exile'))",
    expect_groups=True,
))

results.append(run_case(
    "12. Explicit OR-in-OR parens: A or (B or C and D)  → group for the parens",
    "Metric('Name') == 'folklore' or (Metric('Name') == 'evermore' or Metric('Name') == 'exile' and Metric('State') == 'finished')",
    expect_groups=True,
))

results.append(run_case(
    "13. Explicit AND-in-AND parens: A and (B and C)  → group for the parens",
    "Metric('Name') == 'folklore' and (Metric('Name') == 'evermore' and Metric('State') == 'finished')",
    expect_groups=True,
))

results.append(run_case(
    "14. Double-nested OR parens: A or (B or (C or D and E))",
    "Metric('Name') == 'folklore' or (Metric('Name') == 'evermore' or (Metric('Name') == 'exile' or Metric('Name') == 'evermore' and Metric('State') == 'finished'))",
    expect_groups=True,
))

# ─── Summary ──────────────────────────────────────────────────────────────────

banner("Summary")
for i, status in enumerate(results, 1):
    print(f"  Case {i:2d}: {status}")

passed = sum(1 for s in results if s == "PASS")
failed = sum(1 for s in results if s == "FAIL")
print(f"\n  {passed} passed, {failed} failed out of {len(results)} cases")
