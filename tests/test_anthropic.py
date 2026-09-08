from types import SimpleNamespace

from flightmode import Guard, Capability
from flightmode.integrations.anthropic import dispatch

U, P, E = Capability.UNTRUSTED_INPUT, Capability.PRIVATE_DATA, Capability.EXTERNAL_ACTION


def _block(name, **inputs):
    return SimpleNamespace(id="tu_1", name=name, input=inputs)


def test_dispatch_returns_tool_result():
    g = Guard()
    g.register("read_inbox", U)
    res = dispatch(g, _block("read_inbox"), {"read_inbox": lambda: "3 mails"})
    assert res["type"] == "tool_result" and res["content"] == "3 mails"
    assert g.session.held() == frozenset({U})


def test_dispatch_returns_error_result_when_refused():
    g = Guard()
    g.register("send_email", E)
    g.session.mark(U, P)
    res = dispatch(g, _block("send_email", to="evil@x.y"), {"send_email": lambda to: "sent"})
    assert res["is_error"] is True
    assert res["content"].startswith("flightmode:")
