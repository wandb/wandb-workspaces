"""This is a rewrite of the expression system currently used in Reports.

In a future version, Reports will migrate to this expression syntax.

This module provides both:
1. Object-oriented filter API (FilterExpr, Config, Metric, etc.)
2. String expression parsing for Python-like filter syntax
"""

import ast
import re
import sys
import warnings
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Literal, Optional, Union
from typing import List as LList

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from wandb_workspaces.utils.invertable_dict import InvertableDict

# Type aliases
Ops = Literal[
    "OR", "AND", "=", "!=", "<=", ">=", "<", ">", "IN", "NIN", "==", "WITHINSECONDS"
]


class ReportAPIBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


# Core data models for filters and sorting (hoisted from reports.v2.internal to avoid circular imports)
class Key(ReportAPIBaseModel):
    section: str = "summary"
    name: str = ""


class Filters(ReportAPIBaseModel):
    op: Ops = "OR"
    key: Optional[Key] = None
    filters: Optional[LList["Filters"]] = None
    value: Optional[Any] = None
    disabled: Optional[bool] = None
    current: Optional["Filters"] = None


class SortKeyKey(ReportAPIBaseModel):
    section: str = "run"
    name: str = "createdAt"


class SortKey(ReportAPIBaseModel):
    key: SortKeyKey = Field(default_factory=SortKeyKey)
    ascending: bool = False


__all__ = [
    # Core classes for creating filters and orderings
    "Config",
    "Metric",
    "Summary",
    "Tags",
    "Ordering",
    # Filter expression type (needed for type hints)
    "FilterExpr",
]

Expression = Dict[str, Any]


# Mapping section/function names between string expressions and internal format
section_map = {
    "Config": "config",
    "SummaryMetric": "summary",
    "Summary": "summary",  # Alias for SummaryMetric
    "KeysInfo": "keys_info",
    "Tags": "tags",
    "Metric": "run",
}
# Reversed map uses SummaryMetric as canonical name for 'summary'
section_map_reversed = {
    "config": "Config",
    "summary": "SummaryMetric",
    "keys_info": "KeysInfo",
    "tags": "Tags",
    "run": "Metric",
}

# Mapping metric names between frontend (user-facing) and backend (internal) format
FE_METRIC_NAME_MAP = InvertableDict(
    {
        "ID": "name",
        "Name": "displayName",
        "Tags": "tags",
        "State": "state",
        "CreatedTimestamp": "createdAt",
        "Runtime": "duration",
        "User": "username",
        "Sweep": "sweep",
        "Group": "group",
        "JobType": "jobType",
        "Hostname": "host",
        "UsingArtifact": "inputArtifacts",
        "OutputtingArtifact": "outputArtifacts",
        "Step": "_step",
        "RelativeTime(Wall)": "_absolute_runtime",
        "RelativeTime(Process)": "_runtime",
        "WallTime": "_timestamp",
    }
)

# Legacy name mappings (kept for compatibility)
fe_name_map = dict(FE_METRIC_NAME_MAP)
fe_name_map_reversed = {v: k for k, v in fe_name_map.items()}


# Mapping custom operators to Python operators
OPERATOR_MAP = InvertableDict(
    {
        "AND": "and",
        "OR": "or",
        "=": "==",
        "!=": "!=",
        "<": "<",
        "<=": "<=",
        ">": ">",
        ">=": ">=",
        "IN": "in",
        "NIN": "not in",
        "WITHINSECONDS": "within_last",
    }
)


# ============================================================================
# Time Conversion Utilities
# ============================================================================


def _validate_within_last_field(key: Key) -> None:
    """Validate that within_last is only used with CreatedTimestamp.

    Args:
        key: The Key object representing the field

    Raises:
        ValueError: If the field is not CreatedTimestamp
    """
    # Check both backend and frontend names
    is_created_timestamp = (
        key.name == "createdAt"  # Backend name
        or _convert_be_to_fe_metric_name(key.name)
        == "CreatedTimestamp"  # Frontend name
    )

    if not is_created_timestamp:
        frontend_name = _convert_be_to_fe_metric_name(key.name)
        raise ValueError(
            f"The 'within_last' operator is only available for CreatedTimestamp. "
            f"Cannot use with '{frontend_name}'."
        )


def _convert_time_to_seconds(amount: Union[int, float], unit: str) -> int:
    """Convert a time duration to seconds.

    Args:
        amount: The numeric amount of time
        unit: The time unit - 'minutes', 'hours', or 'days'

    Returns:
        The duration in seconds

    Raises:
        ValueError: If the unit is not recognized
    """
    unit_lower = unit.lower()
    if unit_lower in ("minute", "minutes"):
        return int(amount * 60)
    elif unit_lower in ("hour", "hours"):
        return int(amount * 3600)
    elif unit_lower in ("day", "days"):
        return int(amount * 86400)
    else:
        raise ValueError(
            f"Invalid time unit '{unit}'. Must be 'minutes', 'hours', or 'days'."
        )


def _convert_seconds_to_time(
    seconds: Union[int, float],
) -> tuple[Union[int, float], str]:
    """Convert seconds to the most appropriate time unit.

    Args:
        seconds: The duration in seconds

    Returns:
        A tuple of (amount, unit) where unit is 'minutes', 'hours', or 'days'
    """
    seconds = int(seconds)

    # Choose the largest unit that divides evenly
    if seconds % 86400 == 0:
        return (seconds // 86400, "days")
    elif seconds % 3600 == 0:
        return (seconds // 3600, "hours")
    elif seconds % 60 == 0:
        return (seconds // 60, "minutes")
    else:
        # If no clean division, prefer minutes for small values, hours for medium, days for large
        if seconds < 3600:  # Less than 1 hour
            return (seconds / 60, "minutes")
        elif seconds < 86400:  # Less than 1 day
            return (seconds / 3600, "hours")
        else:
            return (seconds / 86400, "days")


# ============================================================================
# String Expression Parsing Functions
# ============================================================================


def _preprocess_within_last_syntax(expr: str) -> str:
    """
    Preprocess expression to convert within_last operator syntax to function syntax.

    Converts: Metric('CreatedTimestamp') within_last 5 days
    To: WithinLast(Metric('CreatedTimestamp'), 5, 'days')

    This allows users to write more natural-looking time filters.

    Args:
        expr: A filter expression string that may contain within_last operators

    Returns:
        The expression with within_last operators converted to WithinLast() calls
    """
    # Pattern to match: <function_call> within_last <number> <unit>
    # Where function_call is like Metric('...') or Config('...')
    # and unit is minutes, hours, or days (with or without quotes)

    pattern = r"""
        ((?:Metric|Summary|SummaryMetric|Config|KeysInfo|Tags)\s*\([^)]*\))  # Capture the metric call
        \s+within_last\s+                                                      # Match 'within_last' keyword
        (\d+(?:\.\d+)?)                                                        # Capture the number (int or float)
        \s+                                                                     # Whitespace
        (['"]?)                                                                # Optional quote
        (minutes?|hours?|days?)                                                # Capture the unit
        \3                                                                     # Matching quote if present
    """

    def replace_within_last(match):
        metric_call = match.group(1)
        amount = match.group(2)
        unit = match.group(4)

        # Normalize unit to plural form
        if not unit.endswith("s"):
            unit = unit + "s"

        return f"WithinLast({metric_call}, {amount}, '{unit}')"

    result = re.sub(
        pattern, replace_within_last, expr, flags=re.VERBOSE | re.IGNORECASE
    )
    return result


def _preprocess_equality_operators(expr: str) -> str:
    """
    Preprocess expression to convert single '=' to '==' for Python AST parsing.
    This allows users to write 'Config("x") = 5' or 'Config("x") == 5'.
    Both will be mapped to '=' in the backend.

    We need to be careful not to replace '=' in '==', '!=', '<=', or '>='.
    """
    # Replace '=' with '==' only when it's not part of '==', '!=', '<=', or '>='
    # Look behind: not preceded by !, <, >, or =
    # Look ahead: not followed by =
    result = re.sub(r"(?<![!<>=])=(?!=)", "==", expr)
    return result


def _preprocess_comparison_operators(expr: str) -> str:
    """
    Preprocess expression to convert '<' to '<=' and '>' to '>=' for consistency.
    This allows users to write 'x < 5' which will be mapped to '<=' in the backend.

    We need to be careful not to replace '<' or '>' in '<=', '>=', '!=', or '=='.
    """
    original_expr = expr

    # Replace '<' with '<=' only when not already part of '<='
    # Look ahead: not followed by =
    expr = re.sub(r"<(?!=)", "<=", expr)

    # Replace '>' with '>=' only when not already part of '>='
    # Look ahead: not followed by =
    expr = re.sub(r">(?!=)", ">=", expr)

    # Warn if any operators were changed
    if expr != original_expr:
        # Check which operators were mapped
        had_lt = bool(re.search(r"<(?!=)", original_expr))
        had_gt = bool(re.search(r">(?!=)", original_expr))

        if had_lt and had_gt:
            warnings.warn(
                "Filter expression contains '<' and/or '>' operators which are being mapped to '<=' and '>=' respectively for platform consistency. "
                "Consider using '<=' and '>=' explicitly in your filters.",
                UserWarning,
                stacklevel=4,
            )
        elif had_lt:
            warnings.warn(
                "Filter expression contains '<' operator which is being mapped to '<=' for platform consistency. "
                "Consider using '<=' explicitly in your filters.",
                UserWarning,
                stacklevel=4,
            )
        elif had_gt:
            warnings.warn(
                "Filter expression contains '>' operator which is being mapped to '>=' for platform consistency. "
                "Consider using '>=' explicitly in your filters.",
                UserWarning,
                stacklevel=4,
            )

    return expr


def expr_to_filters(expr: str) -> Filters:
    """Parse a string filter expression into an internal Filters tree.

    Args:
        expr: A Python-like filter expression string, e.g.,
            "Config('learning_rate') == 0.001 and State == 'finished'"
            or "Metric('CreatedTimestamp') within_last 5 days"

    Returns:
        An internal Filters tree structure
    """
    if not expr:
        filters = []
    else:
        # Preprocess: Convert within_last operator syntax to function syntax
        # This must happen first, before other transformations
        expr = _preprocess_within_last_syntax(expr)

        # Preprocess: Replace single '=' with '==' for Python AST parsing
        # But avoid replacing '==', '!=', '<=', '>='
        expr = _preprocess_equality_operators(expr)

        # Preprocess: Replace '<' with '<=' and '>' with '>=' for consistency
        expr = _preprocess_comparison_operators(expr)

        parsed_expr = ast.parse(expr, mode="eval")
        root_filter = _parse_node(parsed_expr.body)

        # If the root operation is an AND, unpack its child filters
        if root_filter.op == "AND" and root_filter.filters:
            filters = root_filter.filters
        else:
            filters = [root_filter]

    return Filters(op="OR", filters=[Filters(op="AND", filters=filters)])


def _parse_node(node) -> Filters:
    # Check if this is a WithinLast function call (not inside a comparison)
    if isinstance(node, ast.Call):
        within_last_filter = _handle_within_last_call(node)
        if within_last_filter:
            return within_last_filter

    if isinstance(node, ast.Compare):
        # Check if left side is a function call
        if isinstance(node.left, ast.Call):
            func_call_data = _handle_function_call(node.left)
            # Process the function call data
            if func_call_data:
                section = section_map.get(func_call_data["type"], "default_section")
                name = func_call_data["value"]

                # Handle Tags() which should map to section=run, name=tags
                if func_call_data["type"] == "Tags" and name == "":
                    section = "run"
                    name = "tags"

                key = Key(section=section, name=name)
                # Construct the Filters object
                op = _map_op(node.ops[0])
                right_operand = _extract_value(node.comparators[0])
                return Filters(op=op, key=key, value=right_operand, disabled=False)
            # If func_call_data is falsy, fall back to standard comparison handling
            return _handle_comparison(node)
        else:
            # Handle other cases, e.g., when left side is not a function call
            return _handle_comparison(node)
    elif isinstance(node, ast.BoolOp):
        return _handle_logical_op(node)
    else:
        raise ValueError(f"Unsupported expression type: {type(node)}")


def _map_op(op_node) -> str:
    # Map the AST operation node to a string repr
    # Note: ast.Eq maps to "=" for backend (both "=" and "==" in expressions map to "=")
    op_map = {
        ast.Gt: ">",
        ast.Lt: "<",
        ast.Eq: "=",
        ast.NotEq: "!=",
        ast.GtE: ">=",
        ast.LtE: "<=",
        ast.In: "IN",
        ast.NotIn: "NIN",
    }
    return op_map[type(op_node)]


def _handle_comparison(node) -> Filters:
    # Map operation names to their string representation
    # Note: "Eq" maps to "=" for backend (both "=" and "==" in expressions map to "=")
    op_map = {
        "Gt": ">",
        "Lt": "<",
        "Eq": "=",
        "NotEq": "!=",
        "GtE": ">=",
        "LtE": "<=",
        "In": "IN",
        "NotIn": "NIN",
    }

    left_operand = node.left.id if isinstance(node.left, ast.Name) else None
    left_operand_mapped = to_frontend_name(left_operand)
    right_operand = _extract_value(node.comparators[0])
    operation = type(node.ops[0]).__name__

    return Filters(
        op=op_map.get(operation),
        key=_server_path_to_key(left_operand) if left_operand_mapped else None,
        value=right_operand,
        disabled=False,
    )


def _handle_function_call(node) -> dict:
    if isinstance(node.func, ast.Name):
        func_name = node.func.id
        if func_name in [
            "Config",
            "SummaryMetric",
            "Summary",
            "KeysInfo",
            "Tags",
            "Metric",
        ]:
            # Tags() can be called with no arguments
            if func_name == "Tags" and len(node.args) == 0:
                return {"type": "Tags", "value": ""}
            elif len(node.args) == 1:
                # Handle both ast.Str (Python < 3.8) and ast.Constant (Python 3.8+)
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    arg_value = str(arg.value)
                elif hasattr(ast, "Str") and isinstance(arg, ast.Str):
                    arg_value = str(arg.s)  # type: ignore[attr-defined]
                else:
                    raise ValueError(
                        f"Invalid arguments for {func_name}: expected string literal"
                    )
                return {"type": func_name, "value": arg_value}
            else:
                raise ValueError(f"Invalid arguments for {func_name}")
        else:
            raise ValueError(f"Unsupported function name: {func_name}")
    else:
        raise ValueError("Unsupported function call")


def _handle_within_last_call(node) -> Optional[Filters]:
    """Handle WithinLast(metric_call, amount, unit) function calls.

    Args:
        node: An AST Call node that might be a WithinLast call

    Returns:
        A Filters object with WITHINSECONDS operator, or None if not a WithinLast call
    """
    if not isinstance(node.func, ast.Name) or node.func.id != "WithinLast":
        return None

    if len(node.args) != 3:
        raise ValueError(
            f"WithinLast requires exactly 3 arguments (metric, amount, unit), got {len(node.args)}"
        )

    # First argument should be a metric function call
    metric_call = node.args[0]
    if not isinstance(metric_call, ast.Call):
        raise ValueError(
            "First argument to WithinLast must be a metric function call (e.g., Metric('CreatedTimestamp'))"
        )

    func_call_data = _handle_function_call(metric_call)
    if not func_call_data:
        raise ValueError(
            "First argument to WithinLast must be a valid metric function (Config, Metric, Summary, etc.)"
        )

    section = section_map.get(func_call_data["type"], "default_section")
    name = func_call_data["value"]

    # Handle Tags() which should map to section=run, name=tags
    if func_call_data["type"] == "Tags" and name == "":
        section = "run"
        name = "tags"

    key = Key(section=section, name=name)

    # Validate that this field supports within_last
    _validate_within_last_field(key)

    # Second argument is the amount (numeric)
    amount = _extract_value(node.args[1])
    if not isinstance(amount, (int, float)):
        raise ValueError(
            f"Second argument to WithinLast must be a number, got {type(amount).__name__}"
        )

    # Third argument is the unit (string)
    unit = _extract_value(node.args[2])
    if not isinstance(unit, str):
        raise ValueError(
            f"Third argument to WithinLast must be a string ('minutes', 'hours', or 'days'), got {type(unit).__name__}"
        )

    # Convert to seconds
    seconds = _convert_time_to_seconds(amount, unit)

    return Filters(op="WITHINSECONDS", key=key, value=seconds, disabled=False)


def _extract_value(node) -> Any:
    if sys.version_info < (3, 8) and isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.Constant):
        return node.value  # Use .value not .n for ast.Constant
    if isinstance(node, ast.List) or isinstance(node, ast.Tuple):
        return [_extract_value(element) for element in node.elts]
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.BinOp):
        # Handle binary operations (e.g., 5 + 3, 10 - 2, etc.)
        # Evaluate the operation and return the result
        left = _extract_value(node.left)
        right = _extract_value(node.right)
        bin_op = node.op

        if isinstance(bin_op, ast.Add):
            return left + right
        elif isinstance(bin_op, ast.Sub):
            return left - right
        elif isinstance(bin_op, ast.Mult):
            return left * right
        elif isinstance(bin_op, ast.Div):
            return left / right
        elif isinstance(bin_op, ast.FloorDiv):
            return left // right
        elif isinstance(bin_op, ast.Mod):
            return left % right
        elif isinstance(bin_op, ast.Pow):
            return left**right
        else:
            raise ValueError(f"Unsupported binary operation: {type(bin_op)}")
    if isinstance(node, ast.UnaryOp):
        # Handle unary operations (e.g., -5, +3)
        operand = _extract_value(node.operand)
        unary_op = node.op

        if isinstance(unary_op, ast.UAdd):
            return +operand
        elif isinstance(unary_op, ast.USub):
            return -operand
        else:
            raise ValueError(f"Unsupported unary operation: {type(unary_op)}")
    raise ValueError(f"Unsupported value type: {type(node)}")


def _handle_logical_op(node) -> Filters:
    op = "AND" if isinstance(node.op, ast.And) else "OR"
    filters = [_parse_node(n) for n in node.values]

    return Filters(op=op, filters=filters)


def filters_to_expr(filter_obj: Any, is_root=True) -> str:
    """Convert an internal Filters tree back to a string expression.

    Args:
        filter_obj: An internal Filters tree structure
        is_root: Whether this is the root of the tree (used internally)

    Returns:
        A Python-like filter expression string
    """
    op_map = {
        ">": ">",
        "<": "<",
        "=": "==",
        "==": "==",
        "!=": "!=",
        ">=": ">=",
        "<=": "<=",
        "IN": "in",
        "NIN": "not in",
        "AND": "and",
        "OR": "or",
    }

    def _convert_filter(filter: Any, is_root: bool) -> str:
        if hasattr(filter, "filters") and filter.filters is not None:
            sub_expressions = [
                _convert_filter(f, False)
                for f in filter.filters
                if f.filters is not None or (f.key and f.key.name)
            ]
            if not sub_expressions:
                return ""

            joint = " and " if filter.op == "AND" else " or "
            expr = joint.join(sub_expressions)
            return f"({expr})" if not is_root and sub_expressions else expr
        else:
            if not filter.key or not filter.key.name:
                # Skip filters with empty key names
                return ""

            # Special handling for WITHINSECONDS operator
            if filter.op == "WITHINSECONDS":
                key_name = filter.key.name
                section = filter.key.section

                # Convert backend metric name to frontend name
                frontend_key_name = _convert_be_to_fe_metric_name(key_name)

                # Prepend the function name if the section matches
                if section in section_map_reversed:
                    function_name = section_map_reversed[section]
                    metric_expr = f'{function_name}("{frontend_key_name}")'
                else:
                    metric_expr = frontend_key_name

                # Convert seconds back to human-readable format
                amount, unit = _convert_seconds_to_time(filter.value)
                # Format amount as int if it's a whole number, otherwise as float
                if isinstance(amount, float) and amount.is_integer():
                    amount = int(amount)

                # Use operator syntax for output (more readable)
                return f"{metric_expr} within_last {amount} {unit}"

            key_name = filter.key.name
            section = filter.key.section

            # Convert backend metric name to frontend name
            frontend_key_name = _convert_be_to_fe_metric_name(key_name)

            # Prepend the function name if the section matches
            if section in section_map_reversed:
                function_name = section_map_reversed[section]
                key_name = f'{function_name}("{frontend_key_name}")'
            else:
                key_name = frontend_key_name

            value = filter.value
            if value is None:
                value = "None"
            elif isinstance(value, list):
                value = f"[{', '.join(map(str, value))}]"
            elif isinstance(value, str):
                value = f"'{value}'"

            return f"{key_name} {op_map[filter.op]} {value}"

    return _convert_filter(filter_obj, is_root)


def _key_to_server_path(key: Key):
    name = key.name
    section = key.section
    if section == "config":
        return f"config.{name}"
    elif section == "summary":
        return f"summary_metrics.{name}"
    elif section == "keys_info":
        return f"keys_info.keys.{name}"
    elif section == "tags":
        return f"tags.{name}"
    elif section == "runs":
        return name
    raise ValueError(f"Invalid key ({key})")


def _server_path_to_key(path):
    if path.startswith("config."):
        return Key(section="config", name=path.split("config.", 1)[1])
    elif path.startswith("summary_metrics."):
        return Key(section="summary", name=path.split("summary_metrics.", 1)[1])
    elif path.startswith("keys_info.keys."):
        return Key(section="keys_info", name=path.split("keys_info.keys.", 1)[1])
    elif path.startswith("tags."):
        return Key(section="tags", name=path.split("tags.", 1)[1])
    else:
        return Key(section="run", name=path)


class CustomNodeVisitor(ast.NodeVisitor):
    def visit_Compare(self, node):  # noqa: N802
        left = self.handle_expression(node.left)
        print(f"Expression type: {left}")
        # Continue to handle the comparison operators and right side as needed
        self.generic_visit(node)

    def handle_expression(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in [
                "Config",
                "SummaryMetric",
                "Summary",
                "KeysInfo",
                "Tags",
                "Metric",
            ]:
                # Tags() can be called with no arguments
                if func_name == "Tags" and len(node.args) == 0:
                    return func_name, ""
                elif len(node.args) == 1:
                    # Handle both ast.Str (Python < 3.8) and ast.Constant (Python 3.8+)
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        arg_value = arg.value
                    elif hasattr(ast, "Str") and isinstance(arg, ast.Str):
                        arg_value = arg.s
                    else:
                        return self.get_full_expression(node)
                    return func_name, arg_value
        return self.get_full_expression(node)

    def get_full_expression(self, node):
        if isinstance(node, ast.Attribute):
            return self.get_full_expression(node.value) + "." + node.attr
        elif isinstance(node, ast.Name):
            return node.id
        else:
            return "ArbitraryExpression"


def to_frontend_name(name):
    return fe_name_map_reversed.get(name, name)


def to_backend_name(name):
    return fe_name_map.get(name, name)


def groupby_str_to_key(group_str: str) -> Key:
    """
    Converts a groupby string into an internal Key object.

    If the input string is in the form "section.metric", it splits it into section and metric.
    Otherwise, it defaults the section to "run".

    To simplify usage, if the section is "config", this function ensures that the backend key
    ends with ".value" (unless already provided).

    Examples:
        "group"              -> Key(section="run", name=to_backend_name("group"))
        "run.group"          -> Key(section="run", name=to_backend_name("group"))
        "config.param"       -> Key(section="config", name=to_backend_name("param") + ".value")
        "config.param.value" -> Key(section="config", name=to_backend_name("param.value"))
        "config.nested.x"    -> Key(section="config", name=to_backend_name("nested.value.x"))
        "summary.metric"     -> Key(section="summary", name=to_backend_name("metric"))
    """
    # Split once to separate the leading section (e.g. "config") from the rest of the path
    parts = group_str.split(".", 1)

    if len(parts) == 2:
        section, key_name = parts
    else:
        section, key_name = "run", parts[0]

    # Convert to backend name first in case the user passed a frontend alias
    key_name = to_backend_name(key_name)

    # Special-case: config parameters require the token ".value" **after the first segment**
    # so that, e.g.  "config.nested.x" -> "config.nested.value.x"
    # The existing logic incorrectly appended the suffix resulting in "nested.x.value".
    # We replicate the behaviour used elsewhere in the codebase (see _metric_to_backend).
    if section == "config":
        segments = key_name.split(".")

        # If the path already contains "value" as the second segment, keep as-is.
        if not (len(segments) >= 2 and segments[1] == "value"):
            first, *rest = segments
            key_name = first + ".value" + ("." + ".".join(rest) if rest else "")

    return Key(section=section, name=key_name)


# ============================================================================
# Object-Oriented Filter API
# ============================================================================


@dataclass(eq=False, frozen=True)
class BaseMetric:
    name: str
    section: ClassVar[str]  # declared in subclasses

    def __eq__(self, other: Any) -> "FilterExpr":  # type: ignore
        return FilterExpr.create("=", self, other)

    def __ne__(self, other: Any) -> "FilterExpr":  # type: ignore
        return FilterExpr.create("!=", self, other)

    def __lt__(self, other: Any) -> "FilterExpr":
        # Map < to <= for consistency with backend behavior
        warnings.warn(
            f"Using '<' operator with {self.__class__.__name__} is being mapped to '<=' for platform consistency. "
            "Consider using '<=' explicitly in your filters.",
            UserWarning,
            stacklevel=2,
        )
        return FilterExpr.create("<=", self, other)

    def __le__(self, other: Any) -> "FilterExpr":
        return FilterExpr.create("<=", self, other)

    def __gt__(self, other: Any) -> "FilterExpr":
        # Map > to >= for consistency with backend behavior
        warnings.warn(
            f"Using '>' operator with {self.__class__.__name__} is being mapped to '>=' for platform consistency. "
            "Consider using '>=' explicitly in your filters.",
            UserWarning,
            stacklevel=2,
        )
        return FilterExpr.create(">=", self, other)

    def __ge__(self, other: Any) -> "FilterExpr":
        return FilterExpr.create(">=", self, other)

    def isin(self, other: List[Any]) -> "FilterExpr":
        return FilterExpr.create("IN", self, other)

    def notin(self, other: List[Any]) -> "FilterExpr":
        return FilterExpr.create("NIN", self, other)

    def within_last(
        self, amount: Union[int, float], unit: Literal["minutes", "hours", "days"]
    ) -> "FilterExpr":
        """Filter for runs created within the last N time units.

        This method is only available for CreatedTimestamp.

        Args:
            amount: The numeric amount of time to look back
            unit: The time unit - 'minutes', 'hours', or 'days'

        Returns:
            A FilterExpr using the WITHINSECONDS operator

        Raises:
            ValueError: If used with a field other than CreatedTimestamp

        Example:
            >>> # Filter runs created in the last 5 days
            >>> ws.Metric("CreatedTimestamp").within_last(5, "days")
            >>> # Filter runs created in the last 24 hours
            >>> ws.Metric("CreatedTimestamp").within_last(24, "hours")
        """
        # Validate the field before creating the filter
        key = self.to_key()
        _validate_within_last_field(key)

        seconds = _convert_time_to_seconds(amount, unit)
        return FilterExpr.create("WITHINSECONDS", self, seconds)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}')"

    def to_key(self) -> Key:
        name = _convert_fe_to_be_metric_name(self.name)
        return Key(section=self.section, name=name)

    # TODO: Key and SortKeyKey are actually the same shape, they're just named differently.
    @classmethod
    def from_key(cls, key: Union[Key, SortKeyKey]) -> "MetricType":
        section = key.section
        name = _convert_be_to_fe_metric_name(key.name)
        metric_cls = METRIC_TYPE_MAP.get(section, BaseMetric)
        return metric_cls(name)


@dataclass(eq=False, frozen=True)
class Metric(BaseMetric):
    """Typically metrics that you log with `wandb.log`.

    These also include any metrics that are logged automatically as part of the run, like `Created Timestamp`
    """

    section: ClassVar[Literal["run"]] = "run"


@dataclass(eq=False, frozen=True)
class Summary(BaseMetric):
    """Typically the last value for metrics that you log with `wandb.log`."""

    section: ClassVar[Literal["summary"]] = "summary"


@dataclass(eq=False, frozen=True)
class Config(BaseMetric):
    """Typically the values you log when setting `wandb.config`."""

    section: ClassVar[Literal["config"]] = "config"


@dataclass(eq=False, frozen=True)
class Tags(BaseMetric):
    """The values when setting `wandb.run.tags`.

    Usage: ws.Tags().isin(['tag1', 'tag2'])

    Note: Tags doesn't take a name parameter - it always refers to 'tags' in the run section.
    """

    name: str = "tags"  # Fixed name, always "tags"
    section: ClassVar[Literal["run"]] = "run"  # Tags are in the run section


@dataclass(eq=False, frozen=True)
class KeysInfo(BaseMetric):
    """You probably don't need this.

    This is a special section that contains information about the keys in the other sections.
    """

    section: ClassVar[Literal["keys_info"]] = "keys_info"


METRIC_TYPE_MAP = InvertableDict(
    {
        "run": Metric,
        "summary": Summary,
        "config": Config,
        "keys_info": KeysInfo,
        # Note: Tags is not in this map because it uses section="run"
        # Use Tags() directly or Metric("tags") to filter by tags
    }
)


@dataclass(frozen=True)
class Ordering:
    item: BaseMetric
    ascending: bool = True

    def to_key(self) -> SortKey:
        k = self.item.to_key()
        skk = SortKeyKey(section=k.section, name=k.name)
        return SortKey(key=skk, ascending=self.ascending)

    @classmethod
    def from_key(cls, key: SortKey) -> "Ordering":
        item = BaseMetric.from_key(key.key)
        return cls(item, key.ascending)


@dataclass
class FilterExpr:
    """A converted expression to be used in W&B Filters.

    Don't instantiate this class directly.  Instead, use one of the base metrics above
    (e.g. Metric, Summary, Config, etc) and use the comparison operators to create a FilterExpr

    For example:
      - Metric("loss") < 0.5; or
      - Config("model").isin(["resnet", "densenet"])
    """

    op: str
    key: BaseMetric
    value: Any

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            """Don't instantiate this class directly.  Instead, write an expression using the base metrics, e.g. Metric("loss") < 0.5"""
        )

    @classmethod
    def create(cls, op: str, key: BaseMetric, value: Any):
        key_cls = key.__class__
        mapped_name = _convert_be_to_fe_metric_name(key.name)
        new_key = key_cls(mapped_name)

        instance = cls.__new__(cls)
        instance.op = op
        instance.key = new_key
        instance.value = value
        return instance

    def __repr__(self) -> str:
        return f"({self.key} {OPERATOR_MAP[self.op]} {repr(self.value)})"

    def to_model(self) -> Filters:
        section = self.key.section
        name = _convert_fe_to_be_metric_name(self.key.name)

        return Filters(
            op=self.op,
            key=Key(section=section, name=name),
            value=self.value,
            disabled=False,
        )


def filters_tree_to_filter_expr(tree: Filters) -> List[FilterExpr]:
    def parse_filter(filter: Filters) -> Optional[FilterExpr]:
        if filter.key is None:
            return None
        metric_cls = METRIC_TYPE_MAP.get(filter.key.section, BaseMetric)
        mapped_name = _convert_be_to_fe_metric_name(filter.key.name)
        metric = metric_cls(mapped_name)
        return FilterExpr.create(filter.op, metric, filter.value)

    def parse_expression(expr: Filters) -> List[FilterExpr]:
        if expr.filters:
            filters = []
            for f in expr.filters:
                filters.extend(parse_expression(f))
            return filters
        else:
            return [f for f in [parse_filter(expr)] if f is not None]

    return parse_expression(tree)


def filter_expr_to_filters_tree(filters: List[FilterExpr]) -> Filters:
    def parse_key(metric: BaseMetric) -> Key:
        section = metric.section
        name = _convert_fe_to_be_metric_name(metric.name)
        return Key(section=section, name=name)

    def parse_filter(filter: FilterExpr) -> Filters:
        key = parse_key(filter.key)
        return Filters(op=filter.op, key=key, value=filter.value, disabled=False)

    return Filters(
        op="OR",
        filters=[
            Filters(
                op="AND", filters=[parse_filter(f) for f in filters if f is not None]
            )
        ],
    )


def string_to_filterexpr_list(filter_string: str) -> List[FilterExpr]:
    """Convert a string filter expression to a list of FilterExpr objects.

    This is a convenience function that combines expr_to_filters()
    and filters_tree_to_filter_expr() to provide a direct string → FilterExpr list conversion.

    Args:
        filter_string: A Python-like filter expression string, e.g.,
            "Config('learning_rate') = 0.001 and State = 'finished'"

    Returns:
        A list of FilterExpr objects

    Example:
        >>> filters = string_to_filterexpr_list("Config('lr') = 0.001")
        >>> len(filters)
        1
        >>> filters[0].key.section
        'config'
    """
    if not filter_string:
        return []

    # Convert string expression to internal Filters tree
    filters_tree = expr_to_filters(filter_string)
    # Convert Filters tree to FilterExpr list
    return filters_tree_to_filter_expr(filters_tree)


def filterexpr_list_to_string(filters: List[FilterExpr]) -> str:
    """Convert a list of FilterExpr objects to a string filter expression.

    This is a convenience function that combines filter_expr_to_filters_tree()
    and filters_to_expr() to provide a direct FilterExpr list → string conversion.

    Args:
        filters: A list of FilterExpr objects

    Returns:
        A Python-like filter expression string

    Example:
        >>> from wandb_workspaces import expr
        >>> filters = [expr.Config("learning_rate") == 0.001]
        >>> filterexpr_list_to_string(filters)
        'Config("learning_rate") == 0.001'
    """
    if not filters:
        return ""

    # Convert FilterExpr list to internal Filters tree
    filters_tree = filter_expr_to_filters_tree(filters)
    # Convert Filters tree to string expression
    return filters_to_expr(filters_tree)


def normalize_filters_to_string(instance):
    """Shared model validator that normalizes filters to string format.

    Converts List[FilterExpr] → str while preserving string inputs.
    This creates a unified internal representation across Workspaces and Reports.

    Args:
        instance: The model instance with a 'filters' attribute

    Returns:
        The instance with normalized filters

    Usage:
        @model_validator(mode="after")
        def convert_filterexpr_list_to_string(self):
            return normalize_filters_to_string(self)
    """
    if isinstance(instance.filters, list):
        # Convert FilterExpr list to string
        # This unifies internal representation as string
        filter_string = filterexpr_list_to_string(instance.filters)
        # Update the filters field
        object.__setattr__(instance, "filters", filter_string)
    return instance


def _convert_fe_to_be_metric_name(name: str) -> str:
    return FE_METRIC_NAME_MAP.get(name, name)


def _convert_be_to_fe_metric_name(name: str) -> str:
    return FE_METRIC_NAME_MAP.inv.get(name, name)


MetricType = Union[Metric, Summary, Config, Tags, KeysInfo]
