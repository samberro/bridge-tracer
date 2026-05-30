from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from src.core.schemas import EventModel

_MISSING = object()


@dataclass
class RenderRule:
    name: str
    type_pattern: str
    expression: str
    enabled: bool = True
    max_chars: int = 90
    pin: bool = False

    def matches(self, event: EventModel) -> bool:
        target = f"{event.type} {event.category.value} {event.summary}".casefold()
        pattern = self.type_pattern.strip().casefold()
        if not pattern or pattern == "*":
            return True
        if pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 2:
            try:
                return re.search(pattern[1:-1], target, re.I) is not None
            except re.error:
                return pattern.strip("/") in target
        return pattern in target


DEFAULT_RULES: list[RenderRule] = [
    RenderRule("Last chat message", "llm", "last_message(obj)", enabled=True, max_chars=120, pin=True),
    RenderRule("Tool name", "tool", "coalesce(path(obj, 'details.name'), path(obj, 'details.tool'), path(obj, 'details.function.name'))", enabled=True, max_chars=90, pin=True),
    RenderRule("Tool args", "tool", "coalesce(path(obj, 'details.arguments'), path(obj, 'details.args'), path(obj, 'details.input'))", enabled=True, max_chars=140),
    RenderRule("HTTP status", "http", "coalesce(path(obj, 'details.status_code'), path(obj, 'details.status'), path(obj, 'details.method'))", enabled=True, max_chars=70),
    RenderRule("LLM output", "llm.response", "coalesce(path(obj, 'details.output'), path(obj, 'details.response'), path(obj, 'details.content'))", enabled=True, max_chars=150),
    RenderRule("Error", "error", "coalesce(path(obj, 'details.message'), path(obj, 'details.error'), path(obj, 'summary'))", enabled=True, max_chars=140, pin=True),
]

_RULES: list[RenderRule] = [RenderRule(**rule.__dict__) for rule in DEFAULT_RULES]


def get_rules() -> list[RenderRule]:
    return _RULES


def reset_rules() -> None:
    _RULES[:] = [RenderRule(**rule.__dict__) for rule in DEFAULT_RULES]


def event_payload(event: EventModel) -> dict[str, Any]:
    return event.model_dump(mode="json")


def preview_for_event(event: EventModel, *, max_chars: int = 90) -> str:
    for rule in _RULES:
        if not rule.enabled or not rule.matches(event):
            continue
        value = evaluate_rule(rule, event)
        if value.ok and value.text:
            return _clip(value.text, min(max_chars, rule.max_chars))
    return fallback_preview(event, max_chars=max_chars)


def pinned_values_for_event(event: EventModel) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for rule in _RULES:
        if not rule.enabled or not rule.pin or not rule.matches(event):
            continue
        value = evaluate_rule(rule, event)
        if value.ok and value.text:
            values.append((rule.name, _clip(value.text, rule.max_chars)))
    return values


def title_for_event(event: EventModel, *, max_chars: int = 58) -> str:
    if _looks_like_message_send(event):
        msg = _last_message(event_payload(event))
        if msg not in (None, _MISSING, ""):
            return _clip(str(msg), max_chars)
    return _clip(event.summary or event.type, max_chars)


def fallback_preview(event: EventModel, *, max_chars: int = 90) -> str:
    data = event_payload(event)
    for expr in (
        "details.message",
        "details.error",
        "details.output",
        "details.response",
        "details.content",
        "details.status_code",
        "summary",
        "type",
    ):
        value = path(data, expr)
        if value not in (_MISSING, None, ""):
            return _clip(_stringify(value), max_chars)
    return "unable to evaluate"


@dataclass(frozen=True)
class EvalValue:
    ok: bool
    text: str
    raw: Any = None


def evaluate_rule(rule: RenderRule, event: EventModel) -> EvalValue:
    return evaluate_expression(rule.expression, event)


def evaluate_expression(expression: str, event: EventModel) -> EvalValue:
    expression = (expression or "").strip()
    if not expression:
        return EvalValue(False, "unable to evaluate")
    data = event_payload(event)
    try:
        if expression.startswith("$."):
            value = path(data, expression[2:])
        elif expression.startswith("path:"):
            value = path(data, expression[5:].strip())
        else:
            value = _safe_eval(expression, data)
        if value is _MISSING:
            return EvalValue(False, "unable to evaluate")
        if value is None:
            return EvalValue(True, "null", None)
        return EvalValue(True, _stringify(value), value)
    except Exception:
        return EvalValue(False, "unable to evaluate")


def _safe_eval(expression: str, obj: dict[str, Any]) -> Any:
    tree = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.IfExp,
        ast.Compare, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Subscript,
        ast.Attribute, ast.List, ast.Tuple, ast.Dict, ast.Slice,
        ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    )
    allowed_funcs = {
        "path": path,
        "coalesce": coalesce,
        "last_message": _last_message,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "json": json.dumps,
    }
    allowed_names = {
        "obj": obj,
        "event": obj,
        "details": obj.get("details") or {},
        "null": None,
        "None": None,
        "True": True,
        "False": False,
        **allowed_funcs,
    }
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"unsupported node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in allowed_funcs:
                raise ValueError("unsupported call")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"unsupported name: {node.id}")
    return eval(compile(tree, "<render_rule>", "eval"), {"__builtins__": {}}, allowed_names)


def coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (_MISSING, None, ""):
            return value
    return None


def path(obj: Any, path_expr: str, default: Any = _MISSING) -> Any:
    if obj is None:
        return default
    cur = obj
    for token in _parse_path(path_expr):
        if cur is None:
            return default
        if isinstance(token, int):
            if not isinstance(cur, (list, tuple)):
                return default
            idx = token if token >= 0 else len(cur) + token
            if idx < 0 or idx >= len(cur):
                return default
            cur = cur[idx]
        else:
            if isinstance(cur, dict):
                cur = cur.get(token, default)
            else:
                cur = getattr(cur, token, default)
        if cur is default:
            return default
    return cur


def _parse_path(path_expr: str) -> list[str | int]:
    path_expr = (path_expr or "").strip()
    if path_expr.startswith("$."):
        path_expr = path_expr[2:]
    parts: list[str | int] = []
    for raw in path_expr.split("."):
        if not raw:
            continue
        name = raw
        while "[" in name and "]" in name:
            before, rest = name.split("[", 1)
            if before:
                parts.append(before)
            idx_text, after = rest.split("]", 1)
            idx_text = idx_text.strip()
            if idx_text.startswith("-") or idx_text.isdigit():
                parts.append(int(idx_text))
            else:
                # conditional/index expressions can be added later; fail soft now.
                parts.append(0)
            name = after
        if name:
            parts.append(name)
    return parts


def _last_message(obj: dict[str, Any]) -> Any:
    candidates = [
        path(obj, "details.messages"),
        path(obj, "details.body.messages"),
        path(obj, "details.request.messages"),
        path(obj, "details.payload.messages"),
        path(obj, "details.input.messages"),
    ]
    for messages in candidates:
        if not isinstance(messages, list):
            continue
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").casefold()
            if role not in ("user", "assistant"):
                continue
            content = message.get("content")
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        val = part.get("text") or part.get("content")
                        if val:
                            text_parts.append(str(val))
                    elif part:
                        text_parts.append(str(part))
                content = " ".join(text_parts)
            if content not in (None, ""):
                return content
    return None


def _looks_like_message_send(event: EventModel) -> bool:
    hay = f"{event.type} {event.summary}".casefold()
    return any(word in hay for word in ("request", "send", "message", "completion.create")) and "response" not in hay


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _clip(value: str, max_chars: int) -> str:
    value = " ".join(str(value).split())
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 1)] + "…"
