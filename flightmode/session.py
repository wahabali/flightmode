import threading
import uuid
from typing import Callable, Optional

from .models import Capability, Decision, ALL_CAPABILITIES


class Session:
    """
    Thread-safe capability ledger for one agent session.

    Meta defines a session as one fresh context window. Create one Session per
    context window, share it across every tool call and every parallel branch.
    Child sessions (subagents) inherit the parent's capabilities and report
    their own back up, so a subagent cannot launder a capability.

    Usage:
        session = Session(on_flightmode=lambda s: print("airplane mode on"))
        session.mark(Capability.UNTRUSTED_INPUT)
        session.mark(Capability.PRIVATE_DATA)
        session.is_grounded()   # True: any tool with EXTERNAL_ACTION is now withdrawn
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        on_flightmode: Optional[Callable[["Session"], None]] = None,
        parent: Optional["Session"] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._held: set[Capability] = set(parent.held()) if parent else set()
        self._lock = threading.Lock()
        self._log: list[Decision] = []
        self._on_flightmode = on_flightmode
        self._fired = False
        self._parent = parent

    def held(self) -> frozenset[Capability]:
        with self._lock:
            return frozenset(self._held)

    def mark(self, *capabilities: Capability) -> None:
        """Record that the session now holds these capabilities."""
        fire = False
        with self._lock:
            self._held.update(capabilities)
            if len(self._held) >= 2 and not self._fired:
                self._fired = True
                fire = True
        if self._parent is not None:
            self._parent.mark(*capabilities)
        if fire and self._on_flightmode:
            self._on_flightmode(self)

    def is_grounded(self) -> bool:
        """True once two capabilities are held: the third is now off limits."""
        with self._lock:
            return len(self._held) >= 2

    def would_complete(self, capabilities: frozenset[Capability]) -> bool:
        """Would using these capabilities put all three in one session?"""
        with self._lock:
            return (self._held | set(capabilities)) == ALL_CAPABILITIES

    def missing(self) -> frozenset[Capability]:
        with self._lock:
            return ALL_CAPABILITIES - self._held

    def record(self, decision: Decision) -> None:
        with self._lock:
            self._log.append(decision)

    def log(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "tool": d.tool,
                    "verdict": d.verdict.value,
                    "held": sorted(c.value for c in d.held),
                    "reason": d.reason,
                }
                for d in self._log
            ]

    def child(self, session_id: Optional[str] = None) -> "Session":
        """A subagent session: inherits what this session holds, reports back what it touches."""
        return Session(session_id=session_id, on_flightmode=self._on_flightmode, parent=self)

    def reset(self) -> None:
        """Start a fresh context window. Only call this when the model's context is actually cleared."""
        with self._lock:
            self._held.clear()
            self._log.clear()
            self._fired = False

    def summary(self) -> str:
        held = sorted(c.value for c in self.held())
        state = "FLIGHTMODE" if self.is_grounded() else "OK"
        return f"session {self.session_id}: holds {len(held)}/3 [{', '.join(held) or 'none'}] [{state}]"
