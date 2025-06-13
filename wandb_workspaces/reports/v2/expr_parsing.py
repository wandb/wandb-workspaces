import ast
import sys
from typing import Any

from .internal import Filters, Key

section_map = {
    "Config": "config",
    "SummaryMetric": "summary",
    "KeysInfo": "keys_info",
    "Tags": "tags",
    "Metric": "run",
}
section_map_reversed = {v: k for k, v in section_map.items()}

fe_name_map = {
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
    # "GroupedRuns": "__wb_group_by_all"
}
fe_name_map_reversed = {v: k for k, v in fe_name_map.items()}


def expr_to_filters(expr: str) -> Filters:
    if not expr:
        filters = []
    else:
        parsed_expr = ast.parse(expr, mode="eval")
        root_filter = _parse_node(parsed_expr.body)

        # If the root operation is an AND, unpack its child filters
        if root_filter.op == "AND" and root_filter.filters:
            filters = root_filter.filters
        else:
            filters = [root_filter]

    return Filters(op="OR", filters=[Filters(op="AND", filters=filters)])


def _parse_node(node) -> Filters:
    if isinstance(node, ast.Compare):
        # Check if left side is a function call
        if isinstance(node.left, ast.Call):
            func_call_data = _handle_function_call(node.left)
            # Process the function call data
            if func_call_data:
                section = section_map.get(func_call_data["type"], "default_section")
                key = Key(section=section, name=func_call_data["value"])
                # Construct the Filters object
                op = _map_op(node.ops[0])
                right_operand = _extract_value(node.comparators[0])
                return Filters(op=op, key=key, value=right_operand, disabled=False)
        else:
            # Handle other cases, e.g., when left side is not a function call
            return _handle_comparison(node)
    elif isinstance(node, ast.BoolOp):
        return _handle_logical_op(node)
    else:
        raise ValueError(f"Unsupported expression type: {type(node)}")


def _map_op(op_node) -> str:
    # Map the AST operation node to a string repr
    op_map = {
        ast.Gt: ">",
        ast.Lt: "<",
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.GtE: ">=",
        ast.LtE: "<=",
        ast.In: "IN",
        ast.NotIn: "NIN",
    }
    return op_map[type(op_node)]


def _handle_comparison(node) -> Filters:
    op_map = {
        "Gt": ">",
        "Lt": "<",
        "Eq": "==",
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
        if func_name in ["Config", "SummaryMetric", "KeysInfo", "Tags", "Metric"]:
            if len(node.args) == 1 and isinstance(node.args[0], ast.Str):
                arg_value = node.args[0].s
                return {"type": func_name, "value": arg_value}
            else:
                raise ValueError(f"Invalid arguments for {func_name}")
    else:
        raise ValueError("Unsupported function call")


def _extract_value(node) -> Any:
    if sys.version_info < (3, 8) and isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.Constant):
        return node.n
    if isinstance(node, ast.List) or isinstance(node, ast.Tuple):
        return [_extract_value(element) for element in node.elts]
    if isinstance(node, ast.Name):
        return node.id
    raise ValueError(f"Unsupported value type: {type(node)}")


def _handle_logical_op(node) -> Filters:
    op = "AND" if isinstance(node.op, ast.And) else "OR"
    filters = [_parse_node(n) for n in node.values]

    return Filters(op=op, filters=filters)


def filters_to_expr(filter_obj: Any, is_root=True) -> str:
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

            key_name = filter.key.name
            section = filter.key.section

            # Prepend the function name if the section matches
            if section in section_map_reversed:
                function_name = section_map_reversed[section]
                key_name = f'{function_name}("{key_name}")'

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
    # raise ValueError(f"Invalid {key=}")


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
            if func_name in ["Config", "SummaryMetric", "KeysInfo", "Tags", "Metric"]:
                if len(node.args) == 1 and isinstance(node.args[0], ast.Str):
                    arg_value = node.args[0].s
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
