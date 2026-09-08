import time
from dataclasses import dataclass, field
from enum import Enum


class Capability(str, Enum):
    """
    The three properties from Meta's Agents Rule of Two.
    An agent may hold at most two of them within one session.
    """
    UNTRUSTED_INPUT = "untrusted_input"    # reads content the user did not write: email, web, shared files
    PRIVATE_DATA = "private_data"          # touches sensitive systems or private data
    EXTERNAL_ACTION = "external_action"    # changes state or communicates outside the session


ALL_CAPABILITIES: frozenset[Capability] = frozenset(Capability)


class Verdict(str, Enum):
    ALLOW = "allow"
    WITHDRAW = "withdraw"      # tool removed from the tools array before the model sees it
    ESCALATE = "escalate"      # tool call routed to a human approver
    DENY = "deny"              # human declined, or no approver configured


class Mode(str, Enum):
    WITHDRAW = "withdraw"      # default: the third capability disappears, no question asked
    APPROVE = "approve"        # the third capability goes to a human


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capabilities: frozenset[Capability]

    def __str__(self) -> str:
        caps = ", ".join(sorted(c.value for c in self.capabilities)) or "none"
        return f"{self.name} [{caps}]"


@dataclass
class Decision:
    tool: str
    verdict: Verdict
    held: frozenset[Capability]
    would_hold: frozenset[Capability]
    reason: str
    timestamp: float = field(default_factory=time.time)

    @property
    def allowed(self) -> bool:
        return self.verdict == Verdict.ALLOW

    def __str__(self) -> str:
        return f"{self.verdict.value.upper():8} {self.tool}: {self.reason}"
