import json
from datetime import date, timedelta

GEN = 10**18
C = "contracts/parametric_weather_cover.py"
LAT, LON = -62000, 1068500  # Jakarta


def _series(start, end, value_fn, var="precipitation_sum"):
    days, vals = [], []
    d = start
    while d <= end:
        days.append(d.isoformat())
        vals.append(value_fn(d))
        d += timedelta(days=1)
    return {"status": 200, "body": json.dumps({"daily": {"time": days, var: vals}})}


def _mock_history(vm, window_start, window_end, wet_years, wet=30.0, dry=1.0):
    """10 years of history; in `wet_years` every day of the window gets `wet` mm."""
    first = window_start.replace(year=window_start.year - 10)
    last = window_end.replace(year=window_end.year - 1)

    def v(d):
        in_window = (d.month, d.day) >= (window_start.month, window_start.day) and \
                    (d.month, d.day) <= (window_end.month, window_end.day)
        return wet if (in_window and d.year in wet_years) else dry

    vm.mock_web(rf".*start_date={first.isoformat()}.*", _series(first, last, v))


def _mock_observed(vm, start, end, mm_per_day):
    vm.mock_web(rf".*start_date={start.isoformat()}&end_date={end.isoformat()}.*",
                _series(start, end, lambda d: mm_per_day))


def _setup(vm, deploy, alice, backdated=False, liquidity=100 * GEN):
    c = deploy(C)
    vm.sender = alice
    pid = c.create_pool("Jakarta rain", 2000, 2500, backdated)
    vm.value = liquidity
    c.deposit(pid)
    vm.value = 0
    return c, pid


def test_pool_deposit_and_shares(direct_vm, direct_deploy, direct_alice):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice)
    p = c.get_pool(pid)
    assert p["balance"] == str(100 * GEN) and p["free"] == str(100 * GEN)
    assert c.get_shares(pid, direct_alice.as_hex if hasattr(direct_alice, "as_hex") else "0x" + direct_alice.hex()) == str(100 * GEN)


def test_actuarial_premium_and_trigger_payout(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 10, 20), date(2026, 10, 26)
    _mock_history(direct_vm, s, e, wet_years={2018, 2021})  # 2/10 years triggered
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * GEN  # max premium; excess refunded
    r = c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 1000, 10 * GEN)
    direct_vm.value = 0
    # (2*2+1)/(2*11) * 1.2 * 10 GEN = 2.7272.. GEN
    assert r["hits"] == 2 and r["years"] == 10
    assert int(r["premium"]) == 10 * GEN * 5 * 12000 // (22 * 10000)
    pool = c.get_pool(pid)
    assert pool["locked"] == str(10 * GEN)
    assert int(pool["balance"]) == 100 * GEN + int(r["premium"])

    _mock_observed(direct_vm, s, e, 20.0)  # 140 mm >= 100 mm
    out = c.settle(r["policy_id"])
    assert out["status"] == "PAID" and out["observed_x10"] == 1400
    pol = c.get_policy(r["policy_id"])
    assert pol["status"] == "PAID" and pol["pricing"]["hits"] == 2
    pool = c.get_pool(pid)
    assert pool["locked"] == "0" and pool["claims_paid"] == str(10 * GEN)
    assert int(pool["balance"]) == 90 * GEN + int(r["premium"])
    with direct_vm.expect_revert("already settled"):
        c.settle(r["policy_id"])


def test_no_trigger_releases_lock_and_premium_accrues(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 10, 1), date(2026, 10, 3)
    _mock_history(direct_vm, s, e, wet_years=set())
    direct_vm.sender = direct_bob
    direct_vm.value = GEN
    r = c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_max_day", True, 500, 4 * GEN)
    direct_vm.value = 0
    _mock_observed(direct_vm, s, e, 2.0)
    out = c.settle(r["policy_id"])
    assert out["status"] == "EXPIRED"
    pool = c.get_pool(pid)
    assert pool["locked"] == "0" and pool["claims_paid"] == "0"
    # underwriter can now withdraw everything, including the premium
    direct_vm.sender = direct_alice
    got = c.withdraw(pid, 100 * GEN)
    assert got == 100 * GEN + int(r["premium"])


def test_locked_liquidity_cannot_be_withdrawn(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True, liquidity=40 * GEN)
    s, e = date(2026, 9, 1), date(2026, 9, 2)
    _mock_history(direct_vm, s, e, wet_years=set())
    direct_vm.sender = direct_bob
    direct_vm.value = GEN
    c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 800, 10 * GEN)
    direct_vm.value = 0
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("locked"):
        c.withdraw(pid, 40 * GEN)
    assert c.withdraw(pid, 20 * GEN) == 20 * GEN * (40 * GEN + int(c.get_policy(0)["premium"])) // (40 * GEN)


def test_capacity_and_uninsurable(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 8, 1), date(2026, 8, 5)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("capacity"):  # 25% of 100 GEN max
        c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 100, 30 * GEN)
    _mock_history(direct_vm, s, e, wet_years=set(range(2016, 2026)))
    direct_vm.value = 10 * GEN
    with direct_vm.expect_revert("uninsurable"):
        c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 100, 10 * GEN)


def test_premium_must_be_attached(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 7, 1), date(2026, 7, 7)
    _mock_history(direct_vm, s, e, wet_years={2017})
    direct_vm.sender = direct_bob
    direct_vm.value = 1
    with direct_vm.expect_revert("premium is"):
        c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 1000, 10 * GEN)


def test_backdating_blocked_and_settle_waits_for_data(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=False)
    direct_vm.warp("2026-11-02T00:00:00Z")
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("start after today"):
        c.buy_policy(pid, LAT, LON, "2026-11-01", "2026-11-03", "rain_total", True, 1000, GEN)
    s, e = date(2026, 11, 10), date(2026, 11, 12)
    _mock_history(direct_vm, s, e, wet_years={2019})
    direct_vm.value = GEN
    r = c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 1000, 4 * GEN)
    direct_vm.value = 0
    direct_vm.warp("2026-11-13T00:00:00Z")
    with direct_vm.expect_revert("not final"):
        c.settle(r["policy_id"])
    direct_vm.warp("2026-11-16T00:00:00Z")
    # data still has a null day -> transient error, nothing settles
    direct_vm.mock_web(r".*start_date=2026-11-10&end_date=2026-11-12.*", {"status": 200, "body": json.dumps(
        {"daily": {"time": ["2026-11-10", "2026-11-11", "2026-11-12"], "precipitation_sum": [50.0, None, 60.0]}})})
    with direct_vm.expect_revert("incomplete"):
        c.settle(r["policy_id"])
    assert c.get_policy(r["policy_id"])["status"] == "ACTIVE"


def test_cold_trigger_below(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 1, 10), date(2026, 1, 12)
    first, last = date(2016, 1, 10), date(2025, 1, 12)
    direct_vm.mock_web(rf".*start_date={first}.*", _series(first, last, lambda d: 5.0, "temperature_2m_min"))
    direct_vm.sender = direct_bob
    direct_vm.value = GEN
    r = c.buy_policy(pid, 522000, 210000, s.isoformat(), e.isoformat(), "temp_min", False, -100, 5 * GEN)
    direct_vm.value = 0
    assert r["hits"] == 0
    direct_vm.mock_web(rf".*start_date={s}&end_date={e}.*",
                       {"status": 200, "body": json.dumps({"daily": {"time": [str(s), "2026-01-11", str(e)],
                                                                      "temperature_2m_min": [-3.0, -12.4, -8.0]}})})
    out = c.settle(r["policy_id"])
    assert out["status"] == "PAID" and out["observed_x10"] == -124


def test_settle_validator_rejects_wrong_verdict_and_far_value(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 10, 20), date(2026, 10, 26)
    _mock_history(direct_vm, s, e, wet_years={2018})
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * GEN
    r = c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 1000, 10 * GEN)
    direct_vm.value = 0
    _mock_observed(direct_vm, s, e, 20.0)  # 140.0 mm
    c.settle(r["policy_id"])
    assert direct_vm.run_validator() is True
    # leader claims "not triggered" -> verdict mismatch
    assert direct_vm.run_validator(leader_result={"value_x10": 1400, "triggered": False}) is False
    # leader verdict inconsistent with its own value
    assert direct_vm.run_validator(leader_result={"value_x10": 900, "triggered": True}) is False
    # value within tolerance (max(0.5mm, 3% of 100mm = 3mm)) is accepted, beyond it is not
    assert direct_vm.run_validator(leader_result={"value_x10": 1425, "triggered": True}) is True
    assert direct_vm.run_validator(leader_result={"value_x10": 1500, "triggered": True}) is False


def test_pricing_validator_checks_hit_count(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, pid = _setup(direct_vm, direct_deploy, direct_alice, backdated=True)
    s, e = date(2026, 10, 20), date(2026, 10, 26)
    _mock_history(direct_vm, s, e, wet_years={2018, 2020, 2022})
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * GEN
    r = c.buy_policy(pid, LAT, LON, s.isoformat(), e.isoformat(), "rain_total", True, 1000, 10 * GEN)
    assert r["hits"] == 3
    assert direct_vm.run_validator(index=-1) is True
    hist = c.get_policy(r["policy_id"])["pricing"]["history"]
    forged = [[y, 10] for y, _ in hist]  # leader claims a dry history -> 0 hits
    assert direct_vm.run_validator(leader_result={"years": 10, "hits": 0, "history": forged}) is False
    # hits must match the leader's own history
    assert direct_vm.run_validator(leader_result={"years": 10, "hits": 0, "history": hist}) is False
