from flightmode import Session, Capability, ALL_CAPABILITIES

U, P, E = Capability.UNTRUSTED_INPUT, Capability.PRIVATE_DATA, Capability.EXTERNAL_ACTION


def test_new_session_holds_nothing():
    s = Session()
    assert s.held() == frozenset()
    assert not s.is_grounded()


def test_two_capabilities_ground_the_session():
    s = Session()
    s.mark(U)
    assert not s.is_grounded()
    s.mark(P)
    assert s.is_grounded()
    assert s.missing() == frozenset({E})


def test_would_complete():
    s = Session()
    s.mark(U, P)
    assert s.would_complete(frozenset({E}))
    assert not s.would_complete(frozenset({U}))
    assert not s.would_complete(frozenset({P}))


def test_on_flightmode_fires_once():
    fired = []
    s = Session(on_flightmode=lambda sess: fired.append(sess.session_id))
    s.mark(U)
    s.mark(P)
    s.mark(P)
    s.mark(E)
    assert len(fired) == 1


def test_child_inherits_parent_capabilities():
    parent = Session()
    parent.mark(U)
    child = parent.child()
    assert child.held() == frozenset({U})


def test_child_reports_back_to_parent():
    parent = Session()
    child = parent.child()
    child.mark(P)
    assert parent.held() == frozenset({P})
    child.mark(U)
    assert parent.is_grounded()


def test_reset_clears_everything():
    s = Session()
    s.mark(U, P)
    s.reset()
    assert s.held() == frozenset()
    assert not s.is_grounded()
    s.mark(U, P)
    assert s.is_grounded()


def test_summary_mentions_state():
    s = Session(session_id="abc")
    assert "OK" in s.summary()
    s.mark(U, P)
    assert "FLIGHTMODE" in s.summary()


def test_all_capabilities_is_three():
    assert len(ALL_CAPABILITIES) == 3
