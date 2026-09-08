import pytest

from flightmode import Guard, Capability, FlightmodeError
from flightmode.integrations.langgraph import flightmode_node

U, P, E = Capability.UNTRUSTED_INPUT, Capability.PRIVATE_DATA, Capability.EXTERNAL_ACTION


def test_node_injects_guard_and_marks_session():
    guard = Guard()

    @flightmode_node(guard, U, step_label="read_inbox")
    def read_inbox(state, guard, session):
        return {**state, "mail": ["x"]}

    out = read_inbox({})
    assert out["mail"] == ["x"]
    assert guard.session.held() == frozenset({U})
    assert guard.spec("read_inbox").capabilities == frozenset({U})


def test_third_node_raises():
    guard = Guard()

    @flightmode_node(guard, U)
    def read_inbox(state, guard, session):
        return state

    @flightmode_node(guard, P)
    def read_crm(state, guard, session):
        return state

    @flightmode_node(guard, E)
    def send_reply(state, guard, session):
        return state

    read_inbox({})
    read_crm({})
    with pytest.raises(FlightmodeError) as exc:
        send_reply({})
    assert exc.value.decision.tool == "send_reply"


def test_node_without_capabilities_never_blocks():
    guard = Guard()
    guard.session.mark(U, P)

    @flightmode_node(guard)
    def summarise(state, guard, session):
        return {**state, "done": True}

    assert summarise({})["done"]
