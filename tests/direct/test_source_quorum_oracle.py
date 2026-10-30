import json

Q = "Did the Python Software Foundation release Python 3.14.0?"
SRC = ["https://a.example.com/news", "https://b.example.com/post", "https://c.example.com/x"]


def _mock(vm, verdict):
    vm.mock_web(r".*\.example\.com.*", {"status": 200, "body": "Python 3.14.0 is now available."})
    vm.mock_llm(r".*checking ONE web source.*", json.dumps({"verdict": verdict, "quote": "3.14.0 is now available"}))


def _new(vm, deploy, who, tip=0):
    c = deploy("contracts/source_quorum_oracle.py")
    vm.sender = who
    vm.value = tip
    cid = c.ask(Q, "Yes only if a final 3.14.0 release is announced.", SRC, 2, 0, 30 * 86400)
    vm.value = 0
    return c, cid


def test_ask_and_view(direct_vm, direct_deploy, direct_alice):
    c, cid = _new(direct_vm, direct_deploy, direct_alice, tip=10**18)
    d = c.get_claim(cid)
    assert d["outcome"] == "PENDING" and d["min_agree"] == 2 and len(d["sources"]) == 3
    assert d["tip"] == str(10**18)


def test_resolves_yes_with_quorum(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, cid = _new(direct_vm, direct_deploy, direct_alice, tip=10**18)
    _mock(direct_vm, "YES")
    direct_vm.sender = direct_bob
    r = c.resolve(cid)
    assert r["outcome"] == "YES"
    assert c.get_outcome(cid) == "YES"
    assert len(c.get_claim(cid)["per_source"]) == 3
    with direct_vm.expect_revert("already settled"):
        c.resolve(cid)


def test_unclear_stays_pending_and_cooldown(direct_vm, direct_deploy, direct_alice):
    c, cid = _new(direct_vm, direct_deploy, direct_alice)
    _mock(direct_vm, "UNCLEAR")
    r = c.resolve(cid)
    assert r["outcome"] == "PENDING" and r["attempts"] == 1
    with direct_vm.expect_revert("cooldown"):
        c.resolve(cid)


def test_validation(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy("contracts/source_quorum_oracle.py")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("https URLs"):
        c.ask(Q, "", ["http://x.com"], 1, 0, 86400)
    with direct_vm.expect_revert("min_agree"):
        c.ask(Q, "", SRC, 4, 0, 86400)
    with direct_vm.expect_revert("duplicate"):
        c.ask(Q, "", [SRC[0], SRC[0]], 1, 0, 86400)


def test_not_expired(direct_vm, direct_deploy, direct_alice):
    c, cid = _new(direct_vm, direct_deploy, direct_alice)
    with direct_vm.expect_revert("not expired"):
        c.expire(cid)
