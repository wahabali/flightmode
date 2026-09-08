from typing import Any, Callable

from ..guard import Guard, FlightmodeError


def dispatch(guard: Guard, tool_use: Any, handlers: dict[str, Callable]) -> dict:
    """
    Execute one Anthropic `tool_use` content block through the guard and
    return the matching `tool_result` block.

    If the call is refused, the model gets an error result instead of an
    exception, so the loop can continue and the model can explain itself.

    Usage:
        for block in response.content:
            if block.type == "tool_use":
                results.append(dispatch(guard, block, {"read_inbox": read_inbox, ...}))
    """
    name = tool_use.name
    fn = handlers[name]
    try:
        output = guard.run(name, fn, **(tool_use.input or {}))
        return {"type": "tool_result", "tool_use_id": tool_use.id, "content": str(output)}
    except FlightmodeError as e:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "is_error": True,
            "content": f"flightmode: {e.decision.reason}",
        }
