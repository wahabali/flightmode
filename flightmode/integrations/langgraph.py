import functools
from typing import Callable, Optional

from ..guard import Guard, FlightmodeError
from ..models import Capability


def flightmode_node(
    guard: Guard,
    *capabilities: Capability,
    step_label: Optional[str] = None,
) -> Callable:
    """
    Decorator for a LangGraph StateGraph node function.

    Declares which capabilities the node uses. Before the node runs, the guard
    checks whether those capabilities would complete the triangle and raises
    FlightmodeError if so. After the node runs, the session is marked.
    Injects `guard` and `session` as keyword arguments.

    Usage:
        guard = Guard()

        @flightmode_node(guard, Capability.UNTRUSTED_INPUT, step_label="read_inbox")
        def read_inbox_node(state: dict, guard: Guard, session: Session) -> dict:
            ...

        @flightmode_node(guard, Capability.EXTERNAL_ACTION, step_label="send_reply")
        def send_node(state: dict, guard: Guard, session: Session) -> dict:
            tools, withdrawn = guard.filter_tools(TOOLS)
            ...
    """

    def decorator(fn: Callable) -> Callable:
        name = step_label or fn.__name__
        guard.register(name, *capabilities)

        @functools.wraps(fn)
        def wrapper(state, **kwargs):
            decision = guard.check(name)
            if not decision.allowed:
                raise FlightmodeError(decision)
            result = fn(state, guard=guard, session=guard.session, **kwargs)
            if capabilities:
                guard.session.mark(*capabilities)
            return result

        wrapper.__flightmode_node__ = True
        wrapper.__step_label__ = name
        return wrapper

    return decorator
