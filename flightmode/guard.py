import functools
from typing import Any, Callable, Optional

from .models import Capability, Decision, Mode, ToolSpec, Verdict
from .session import Session


class FlightmodeError(Exception):
    """Raised when a tool call would give the session all three capabilities."""

    def __init__(self, decision: Decision):
        self.decision = decision
        super().__init__(str(decision))


def _tool_name(tool: dict) -> Optional[str]:
    # Anthropic: {"name": ...}   OpenAI: {"type": "function", "function": {"name": ...}}
    if "name" in tool:
        return tool["name"]
    fn = tool.get("function")
    if isinstance(fn, dict):
        return fn.get("name")
    return None


class Guard:
    """
    Enforces the Rule of Two for one session.

    Register each tool with the capabilities it carries. Then, before every
    model call, pass your tools array through `filter_tools()`: any tool that
    would complete the triangle is removed, so the model cannot even ask for it.
    Wrap tool functions with `@guard.tool(...)` so executions are checked and
    the session ledger is updated automatically.

    Usage:
        guard = Guard()

        @guard.tool(Capability.UNTRUSTED_INPUT)
        def read_inbox(): ...

        @guard.tool(Capability.PRIVATE_DATA)
        def read_crm(customer_id): ...

        @guard.tool(Capability.EXTERNAL_ACTION)
        def send_email(to, body): ...

        tools, withdrawn = guard.filter_tools(TOOLS)   # before each messages.create()
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        mode: Mode = Mode.WITHDRAW,
        approver: Optional[Callable[[Decision], bool]] = None,
        on_withdraw: Optional[Callable[[Decision], None]] = None,
    ):
        self.session = session or Session()
        self.mode = Mode(mode)
        self._approver = approver
        self._on_withdraw = on_withdraw
        self._tools: dict[str, ToolSpec] = {}

    # ---- registration -------------------------------------------------

    def register(self, name: str, *capabilities: Capability) -> ToolSpec:
        spec = ToolSpec(name=name, capabilities=frozenset(capabilities))
        self._tools[name] = spec
        return spec

    def spec(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def tool(self, *capabilities: Capability, name: Optional[str] = None) -> Callable:
        """Decorator: register a tool function and guard every execution of it."""

        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            self.register(tool_name, *capabilities)

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return self.run(tool_name, fn, *args, **kwargs)

            wrapper.__flightmode_tool__ = tool_name
            return wrapper

        return decorator

    # ---- decisions ----------------------------------------------------

    def check(self, tool_name: str) -> Decision:
        """Decide whether this tool may run right now. Records the decision."""
        held = self.session.held()
        spec = self._tools.get(tool_name)

        if spec is None:
            decision = Decision(
                tool=tool_name, verdict=Verdict.ALLOW, held=held, would_hold=held,
                reason="unregistered tool, no capabilities declared",
            )
            self.session.record(decision)
            return decision

        would_hold = frozenset(held | spec.capabilities)
        if len(would_hold) < 3:
            decision = Decision(
                tool=tool_name, verdict=Verdict.ALLOW, held=held, would_hold=would_hold,
                reason="within the Rule of Two",
            )
            self.session.record(decision)
            return decision

        new = sorted(c.value for c in spec.capabilities - held)
        base = (
            f"session already holds {', '.join(sorted(c.value for c in held))}; "
            f"this tool adds {', '.join(new)} and would complete the triangle"
        )

        if self.mode == Mode.APPROVE:
            decision = Decision(
                tool=tool_name, verdict=Verdict.ESCALATE, held=held, would_hold=would_hold,
                reason=base,
            )
            if self._approver is None:
                decision.verdict = Verdict.DENY
                decision.reason = base + " (no approver configured)"
            elif self._approver(decision):
                decision.verdict = Verdict.ALLOW
                decision.reason = base + " (approved by human)"
            else:
                decision.verdict = Verdict.DENY
                decision.reason = base + " (declined by human)"
        else:
            decision = Decision(
                tool=tool_name, verdict=Verdict.WITHDRAW, held=held, would_hold=would_hold,
                reason=base,
            )
            if self._on_withdraw:
                self._on_withdraw(decision)

        self.session.record(decision)
        return decision

    def run(self, tool_name: str, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Check, execute, then mark the session with the tool's capabilities."""
        decision = self.check(tool_name)
        if not decision.allowed:
            raise FlightmodeError(decision)
        result = fn(*args, **kwargs)
        spec = self._tools.get(tool_name)
        if spec is not None and spec.capabilities:
            self.session.mark(*spec.capabilities)
        return result

    # ---- the signature move: prevent before the call ----------------------

    def filter_tools(self, tools: list[dict]) -> tuple[list[dict], list[str]]:
        """
        Remove every tool that would complete the triangle from a tools array.
        Works on Anthropic and OpenAI tool schemas. Call this before each model
        call; the model never sees a tool it is not allowed to use.

        Returns (kept_tools, withdrawn_names).
        """
        kept: list[dict] = []
        withdrawn: list[str] = []
        held = self.session.held()
        for tool in tools:
            name = _tool_name(tool)
            spec = self._tools.get(name) if name else None
            if spec is not None and len(held | spec.capabilities) == 3:
                withdrawn.append(name)
                decision = Decision(
                    tool=name, verdict=Verdict.WITHDRAW, held=held,
                    would_hold=frozenset(held | spec.capabilities),
                    reason="removed from tools array before the call",
                )
                self.session.record(decision)
                if self._on_withdraw:
                    self._on_withdraw(decision)
            else:
                kept.append(tool)
        return kept, withdrawn

    def withdrawn(self) -> list[str]:
        """Names of registered tools that are currently off limits."""
        held = self.session.held()
        return [s.name for s in self._tools.values() if len(held | s.capabilities) == 3]
