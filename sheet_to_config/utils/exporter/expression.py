"""Small parser for TypeDefinition calls and field constraints."""

from dataclasses import dataclass
from typing import Iterable, Tuple


class ExpressionSyntaxError(ValueError):
    """Raised when a TypeDefinition expression cannot be parsed."""

    def __init__(self, message: str, code: str = "SYNTAX_ERROR"):
        super().__init__(message)
        self.code = code


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
        if char in ("(", "\uff08"):
            depth += 1
            current.append(char)
            continue
        if char in (")", "\uff09"):
            depth -= 1
            if depth < 0:
                raise ExpressionSyntaxError(
                    "Unmatched closing parenthesis",
                    code="UNMATCHED_CLOSING_PARENTHESIS",
                )
            current.append(char)
            continue
        if char in delimiter_set and depth == 0:
            result.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if quote:
        raise ExpressionSyntaxError(
            "Unterminated quoted string", code="UNTERMINATED_QUOTE"
        )
    if depth != 0:
        raise ExpressionSyntaxError(
            "Unmatched opening parenthesis",
            code="UNMATCHED_OPENING_PARENTHESIS",
        )
    result.append("".join(current).strip())
    return result


def parse_call(text: str, arg_delimiters=(',', ';')) -> CallExpression:
    source = (text or "").strip()
    if not source:
        raise ExpressionSyntaxError("Expression is empty")
    open_index = next(
        (index for index, char in enumerate(source) if char in ("(", "\uff08")),
        -1,
    )
    if open_index < 0:
        if any(char in source for char in (")", "\uff09")):
            raise ExpressionSyntaxError(
                "Unmatched closing parenthesis",
                code="UNMATCHED_CLOSING_PARENTHESIS",
            )
        return CallExpression(source)

    close_index = _find_matching_close(source, open_index)
    if close_index != len(source) - 1:
        raise ExpressionSyntaxError(
            "Function call must end with ')'",
            code="FUNCTION_CALL_NOT_CLOSED",
        )
    name = source[:open_index].strip()
    if not name:
        raise ExpressionSyntaxError("Function name is empty", code="EMPTY_FUNCTION_NAME")
    body = source[open_index + 1:close_index]
    args = () if not body.strip() else tuple(split_top_level(body, arg_delimiters))
    if any(not arg for arg in args):
        raise ExpressionSyntaxError(f"Empty argument in {name}()")
    return CallExpression(name, args, True)


def _find_matching_close(source: str, open_index: int) -> int:
    """Return the outer call's closing parenthesis, accepting both widths."""
    depth = 0
    quote = None
    escaped = False

    for index, char in enumerate(source[open_index:], start=open_index):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char in ("(", "\uff08"):
            depth += 1
        elif char in (")", "\uff09"):
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                raise ExpressionSyntaxError(
                    "Unmatched closing parenthesis",
                    code="UNMATCHED_CLOSING_PARENTHESIS",
                )

    if quote:
        raise ExpressionSyntaxError(
            "Unterminated quoted string", code="UNTERMINATED_QUOTE"
        )
    raise ExpressionSyntaxError(
        "Unmatched opening parenthesis",
        code="UNMATCHED_OPENING_PARENTHESIS",
    )


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_field_type(text: str) -> FieldTypeExpression:
    parts = split_top_level((text or "str").strip(), ('+',))
    if not parts or not parts[0]:
        raise ExpressionSyntaxError("Field type is empty", code="EMPTY_FIELD_TYPE")
    base_type = parts[0]
    if any(char in base_type for char in ("(", ")", "\uff08", "\uff09")):
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
