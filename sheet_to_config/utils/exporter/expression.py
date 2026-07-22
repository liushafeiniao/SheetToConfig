"""Small parser for TypeDefinition calls and field constraints."""

from dataclasses import dataclass
from typing import Iterable, Tuple


class ExpressionSyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class CallExpression:
    name: str
    args: Tuple[str, ...] = ()
    is_call: bool = False


@dataclass(frozen=True)
class FieldTypeExpression:
    base_type: str
    constraints: Tuple[CallExpression, ...]


def split_top_level(text: str, delimiters: Iterable[str]) -> list[str]:
    delimiter_set = set(delimiters)
    result = []
    current = []
    depth = 0
    quote = None
    escaped = False

    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
            current.append(char)
            continue
        if char == ")":
            depth -= 1
            if depth < 0:
                raise ExpressionSyntaxError("Unmatched closing parenthesis")
            current.append(char)
            continue
        if char in delimiter_set and depth == 0:
            result.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if quote:
        raise ExpressionSyntaxError("Unterminated quoted string")
    if depth != 0:
        raise ExpressionSyntaxError("Unmatched opening parenthesis")
    result.append("".join(current).strip())
    return result


def parse_call(text: str, arg_delimiters=(',', ';')) -> CallExpression:
    source = (text or "").strip()
    if not source:
        raise ExpressionSyntaxError("Expression is empty")
    open_index = source.find("(")
    if open_index < 0:
        if ")" in source:
            raise ExpressionSyntaxError("Unmatched closing parenthesis")
        return CallExpression(source)
    if not source.endswith(")"):
        raise ExpressionSyntaxError("Function call must end with ')'")
    name = source[:open_index].strip()
    if not name:
        raise ExpressionSyntaxError("Function name is empty")
    body = source[open_index + 1:-1]
    args = () if not body.strip() else tuple(split_top_level(body, arg_delimiters))
    if any(not arg for arg in args):
        raise ExpressionSyntaxError(f"Empty argument in {name}()")
    return CallExpression(name, args, True)


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_field_type(text: str) -> FieldTypeExpression:
    parts = split_top_level((text or "str").strip(), ('+',))
    if not parts or not parts[0]:
        raise ExpressionSyntaxError("Field type is empty")
    base_type = parts[0]
    if "(" in base_type or ")" in base_type:
        raise ExpressionSyntaxError("Field type must be a TypeDefinition name")

    constraints = []
    for source in parts[1:]:
        name = source.split("(", 1)[0].strip()
        delimiters = () if name == "regex" else (',',)
        constraint = parse_call(source, delimiters)
        if not constraint.is_call:
            raise ExpressionSyntaxError(
                f"Constraint '{constraint.name}' must use parentheses"
            )
        constraints.append(constraint)
    return FieldTypeExpression(base_type, tuple(constraints))
