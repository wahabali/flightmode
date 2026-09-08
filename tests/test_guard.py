import threading

import pytest

from flightmode import Guard, Capability, Mode, Verdict, FlightmodeError, Session

U, P, E = Capability.UNTRUSTED_INPUT, Capability.PRIVATE_DATA, Capability.EXTERNAL_ACTION

TOOLS = [
    {"name": "read_inbox", "input_schema": {}},
    {"name": "read_crm", "input_schema": {}},
    {"name": "send_email", "input_schema": {}},
    {"name": "calculator", "input_schema": {}},
]


def _guard(mode=Mode.WITHDRAW, approver=None):
    g = Guard(mode=mode, approver=approver)
    g.register("read_inbox", U)
    g.register("read_crm", P)
    g.register("send_email", E)
    return g


def test_two_capabilities_are_allowed():
    g = _guard()
    assert g.check("read_inbox").allowed
    g.session.mark(U)
    assert g.check("read_crm").allowed
    g.session.mark(P)
    assert g.session.is_grounded()


def test_third_capability_is_withdrawn():
    g = _guard()
    g.session.mark(U, P)
    d = g.check("send_email")
    assert d.verdict == Verdict.WITHDRAW
    assert "complete the triangle" in d.reason


def test_any_order_works():
    g = _guard()
    g.session.mark(E, P)
    assert g.check("read_inbox").verdict == Verdict.WITHDRAW
    assert g.check("read_crm").allowed
    assert g.check("send_email").allowed


def test_already_held_capability_stays_allowed():
    g = _guard()
    g.session.mark(U, P)
    assert g.check("read_inbox").allowed
    assert g.check("read_crm").allowed


def test_unregistered_tool_is_allowed():
    g = _guard()
    g.session.mark(U, P)
    assert g.check("calculator").allowed


def test_run_marks_session_after_execution():
    g = _guard()
    out = g.run("read_inbox", lambda: "mail")
    assert out == "mail"
    assert g.session.held() == frozenset({U})


def test_run_raises_when_withdrawn():
    g = _guard()
    g.session.mark(U, P)
    with pytest.raises(FlightmodeError) as exc:
        g.run("send_email", lambda **kw: "sent", to="x@y.z")
    assert exc.value.decision.verdict == Verdict.WITHDRAW


def test_decorator_registers_and_guards():
    g = Guard()

    @g.tool(U)
    def read_inbox():
        return ["mail"]

    @g.tool(P)
    def read_crm():
        return ["row"]

    @g.tool(E)
    def send_email(to):
        return f"sent to {to}"

    assert g.spec("send_email").capabilities == frozenset({E})
    read_inbox()
    read_crm()
    with pytest.raises(FlightmodeError):
        send_email("evil@x.y")


def test_filter_tools_removes_third_capability():
    g = _guard()
    g.session.mark(U, P)
    kept, withdrawn = g.filter_tools(TOOLS)
    assert withdrawn == ["send_email"]
    assert [t["name"] for t in kept] == ["read_inbox", "read_crm", "calculator"]


def test_filter_tools_keeps_everything_when_not_grounded():
    g = _guard()
    g.session.mark(U)
    kept, withdrawn = g.filter_tools(TOOLS)
    assert withdrawn == []
    assert len(kept) == 4


def test_filter_tools_handles_openai_schema():
    g = _guard()
    g.session.mark(U, P)
    tools = [{"type": "function", "function": {"name": "send_email"}},
             {"type": "function", "function": {"name": "read_crm"}}]
    kept, withdrawn = g.filter_tools(tools)
    assert withdrawn == ["send_email"]
    assert kept[0]["function"]["name"] == "read_crm"


def test_multi_capability_tool():
    g = Guard()
    g.register("fetch_url", U, E)   # reads the web and makes an outbound request
    g.register("read_crm", P)
    g.session.mark(P)
    assert g.check("fetch_url").verdict == Verdict.WITHDRAW
    g2 = Guard()
    g2.register("fetch_url", U, E)
    assert g2.check("fetch_url").allowed


def test_approve_mode_asks_human_and_respects_answer():
    seen = []
    g = _guard(mode=Mode.APPROVE, approver=lambda d: (seen.append(d.tool), True)[1])
    g.session.mark(U, P)
    d = g.check("send_email")
    assert d.allowed and "approved" in d.reason
    assert seen == ["send_email"]

    g2 = _guard(mode=Mode.APPROVE, approver=lambda d: False)
    g2.session.mark(U, P)
    assert g2.check("send_email").verdict == Verdict.DENY


def test_approve_mode_without_approver_denies():
    g = _guard(mode=Mode.APPROVE)
    g.session.mark(U, P)
    assert g.check("send_email").verdict == Verdict.DENY


def test_on_withdraw_callback():
    calls = []
    g = Guard(on_withdraw=lambda d: calls.append(d.tool))
    g.register("send_email", E)
    g.session.mark(U, P)
    g.check("send_email")
    g.filter_tools([{"name": "send_email"}])
    assert calls == ["send_email", "send_email"]


def test_withdrawn_lists_off_limits_tools():
    g = _guard()
    assert g.withdrawn() == []
    g.session.mark(U, P)
    assert g.withdrawn() == ["send_email"]


def test_decisions_are_logged():
    g = _guard()
    g.session.mark(U, P)
    g.check("send_email")
    log = g.session.log()
    assert log[-1]["tool"] == "send_email"
    assert log[-1]["verdict"] == "withdraw"


def test_thread_safety_under_parallel_branches():
    g = _guard()
    errors = []

    def branch(cap):
        try:
            g.session.mark(cap)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=branch, args=(c,)) for c in [U, P] * 50]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert g.session.held() == frozenset({U, P})
    assert g.check("send_email").verdict == Verdict.WITHDRAW


def test_subagent_cannot_launder_capability():
    parent = Session()
    g_parent = Guard(session=parent)
    g_parent.register("send_email", E)
    g_parent.session.mark(U)

    child = parent.child()
    g_child = Guard(session=child)
    g_child.register("read_crm", P)
    g_child.run("read_crm", lambda: "rows")

    # parent never called read_crm, but its subagent did, so the parent is grounded too
    assert parent.is_grounded()
    assert g_parent.check("send_email").verdict == Verdict.WITHDRAW
