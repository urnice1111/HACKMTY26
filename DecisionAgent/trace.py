import json
from typing import Any

from DecisionAgent.Models.structured_output import ToolEvent

TOOL_LABELS = {
    "get_graph_summary": "Reading the area",
    "candidate_paths": "Sketching possible routes",
    "path_cost": "Timing the trip",
    "get_place_context": "Checking the neighborhood",
    "get_numeric_signals": "Looking at live numbers",
    "predict_future": "Guessing how busy it will be",
    "score_path": "Weighing time vs demand",
    "take_decision": "Picking the run",
}

_MAX_ARG_CHARS = 400


def _raw_field(item: Any, name: str) -> Any:
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, dict):
        return raw.get(name)
    return getattr(raw, name, None) if raw is not None else None


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _as_dict(value: Any) -> dict:
    parsed = _parse_jsonish(value)
    return parsed if isinstance(parsed, dict) else {}


def _clip_args(args: dict) -> dict:
    clipped: dict[str, Any] = {}
    for key, val in args.items():
        if key in {"matrix", "coordinates"}:
            continue
        rendered = val if isinstance(val, (str, int, float, bool)) or val is None else json.dumps(val)
        if isinstance(rendered, str) and len(rendered) > _MAX_ARG_CHARS:
            clipped[key] = rendered[:_MAX_ARG_CHARS] + "…"
        else:
            clipped[key] = val
    return clipped


def _tool_ok(output: Any) -> bool:
    data = _as_dict(output)
    if data.get("ok") is False:
        return False
    if "error" in data and data.get("ok") is not True:
        return False
    if isinstance(output, str) and output.lower().startswith("error"):
        return False
    return True


def summarize_tool(tool: str, args: dict, output: Any) -> str:
    data = _as_dict(output)
    if tool == "get_graph_summary":
        return "Looked over the area around the origin."
    if tool == "candidate_paths":
        count = data.get("count")
        if isinstance(count, int):
            return f"Sketched {count} possible routes from the origin."
        paths = data.get("paths")
        if isinstance(paths, list):
            return f"Sketched {len(paths)} possible routes from the origin."
        return "Sketched possible routes from the origin."
    if tool == "path_cost":
        minutes = data.get("total_weight") or data.get("arrival_offset_min")
        if isinstance(minutes, (int, float)):
            rounded = round(minutes)
            return f"Timed a trip of about {rounded} minutes."
        return "Timed a trip."
    if tool == "get_place_context":
        return "Checked what the neighborhood around a stop is like."
    if tool == "get_numeric_signals":
        return "Looked at live numbers for a stop."
    if tool == "predict_future":
        return "Guessed how busy the last stop will be when the vehicle arrives."
    if tool == "score_path":
        return "Weighed how long the drive is against how busy the stop looks."
    if tool == "take_decision":
        chosen = data.get("chosen") if isinstance(data.get("chosen"), dict) else {}
        indexes = chosen.get("indexes") if isinstance(chosen, dict) else None
        if isinstance(indexes, list) and len(indexes) > 1:
            return f"Picked the run that ends at point {indexes[-1]}."
        return "Picked the run to send the vehicle on."
    return TOOL_LABELS.get(tool, f"Used {tool}.")


def extract_events(new_items: list[Any] | None) -> list[ToolEvent]:
    pending: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []

    for item in new_items or []:
        item_type = getattr(item, "type", None)
        if item_type == "tool_call_item":
            name = getattr(item, "tool_name", None) or _raw_field(item, "name") or "unknown"
            call_id = getattr(item, "call_id", None) or _raw_field(item, "call_id") or _raw_field(item, "id")
            args = _as_dict(_raw_field(item, "arguments"))
            record = {"tool": str(name), "args": _clip_args(args), "output": None}
            key = str(call_id) if call_id is not None else f"anon-{len(ordered)}"
            pending[key] = record
            ordered.append(record)
            continue

        if item_type == "tool_call_output_item":
            call_id = getattr(item, "call_id", None) or _raw_field(item, "call_id")
            output = getattr(item, "output", None)
            key = str(call_id) if call_id is not None else None
            record = pending.get(key) if key else None
            if record is None:
                record = {"tool": "unknown", "args": {}, "output": output}
                ordered.append(record)
            else:
                record["output"] = output

    events: list[ToolEvent] = []
    for seq, record in enumerate(ordered, start=1):
        tool = record["tool"]
        args = record.get("args") or {}
        output = record.get("output")
        events.append(
            ToolEvent(
                seq=seq,
                tool=tool,
                label=TOOL_LABELS.get(tool, tool.replace("_", " ").capitalize()),
                summary=summarize_tool(tool, args, output),
                args=args,
                ok=_tool_ok(output) if output is not None else True,
            )
        )
    return events
