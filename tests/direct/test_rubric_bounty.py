import json

GEN = 10**18
CRITERIA = [{"name": "Implements the requested CSV parser", "weight": 3},
            {"name": "Includes unit tests", "weight": 1}]


def _mock(vm, s1, s2, body="def parse_csv(...): ...\n# tests\n"):
    vm.mock_web(r".*gist\.example\.com.*", {"status": 200, "body": body})
    vm.mock_llm(r".*impartial reviewer.*", json.dumps({"scores": [
        {"criterion": 1, "score": s1, "reason": "ok"},
        {"criterion": 2, "score": s2, "reason": "ok"}]}))


def _new(vm, deploy, poster, reward=5 * GEN):
    c = deploy("contracts/rubric_bounty.py")
    vm.sender = poster
    vm.value = reward
    bid = c.create_bounty("CSV parser", "Write a robust CSV parser in Python.",
                          CRITERIA, 70, 7 * 86400)
    vm.value = 0
    return c, bid


def test_create_and_view(direct_vm, direct_deploy, direct_alice):
    c, bid = _new(direct_vm, direct_deploy, direct_alice)
    b = c.get_bounty(bid)
    assert b["status"] == "open" and b["reward"] == str(5 * GEN)
    assert b["criteria"][0]["weight"] == 3
    assert c.get_bounty_count() == 1


def test_requires_reward(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy("contracts/rubric_bounty.py")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("attach GEN"):
        c.create_bounty("t", "d", CRITERIA, 70, 86400)


def test_passing_submission_awards(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid = _new(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_bob
    sid = c.submit(bid, "https://gist.example.com/bob/1")
    _mock(direct_vm, 9, 6)  # (27+6)/4*10 = 82.5 -> 82
    res = c.judge(bid, sid)
    assert res["passed"] is True and res["score"] == 82
    assert c.get_bounty(bid)["status"] == "awarded"
    s = c.get_submission(bid, sid)
    assert s["status"] == "passed" and len(s["breakdown"]) == 2


def test_failing_submission_keeps_open(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid = _new(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_bob
    sid = c.submit(bid, "https://gist.example.com/bob/2")
    _mock(direct_vm, 5, 2)  # (15+2)/4*10 = 42
    res = c.judge(bid, sid)
    assert res["passed"] is False
    assert c.get_bounty(bid)["status"] == "open"
    with direct_vm.expect_revert("already judged"):
        c.judge(bid, sid)


def test_attempt_limit_and_poster_block(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid = _new(direct_vm, direct_deploy, direct_alice)
    with direct_vm.expect_revert("poster cannot submit"):
        c.submit(bid, "https://gist.example.com/a")
    direct_vm.sender = direct_bob
    for i in range(3):
        c.submit(bid, f"https://gist.example.com/b{i}")
    with direct_vm.expect_revert("attempt limit"):
        c.submit(bid, "https://gist.example.com/b9")


def test_rejects_non_https(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid = _new(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("https URL"):
        c.submit(bid, "http://insecure.example.com")


def test_reclaim_only_after_deadline(direct_vm, direct_deploy, direct_alice):
    c, bid = _new(direct_vm, direct_deploy, direct_alice)
    with direct_vm.expect_revert("deadline not reached"):
        c.reclaim(bid)
