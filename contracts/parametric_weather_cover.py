# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
ParametricWeatherCover: a parametric weather-insurance market.

Underwriters pool GEN liquidity and receive pool shares. Buyers purchase a
policy for a location (lat/lon), a date window and a weather trigger, e.g.
"total rainfall over 3-9 Nov at -6.2,106.85 >= 120 mm pays 5 GEN". There is no
claims adjuster: the payout is decided by public weather data that every
validator re-fetches.

Two non-deterministic steps, both checked by custom validators:

1. Pricing (buy_policy). The premium is actuarial, not a flat fee. The leader
   pulls the last PRICING_YEARS years of the same calendar window from the
   Open-Meteo historical archive (ERA5 reanalysis) and counts how many years
   would have triggered. The contract prices the premium in code from that
   count: payout * (hits + 0.5) / (years + 1) * (1 + pool loading). Validators
   re-fetch the history and agree only if the year count matches and the hit
   count is within 1.

2. Settlement (settle). After the window has ended and the data has had
   FINALITY_DAYS to settle, anyone can settle. The leader fetches the
   observed daily series for the window, aggregates the metric (sum / max /
   min) and decides triggered / not triggered. Validators re-fetch and agree
   only if (a) the triggered verdict matches, (b) the leader's verdict follows
   from the leader's own value and the policy threshold, and (c) the values
   are within VALUE_TOLERANCE. Incomplete data (nulls) is a transient error,
   so a policy can never be settled on partial data.

Pool accounting: balance = all GEN held for the pool (free + locked).
Each policy locks its payout; settlement either pays the buyer from the lock
or releases it. Underwriters can only withdraw free liquidity, at the current
share price, so premiums and losses accrue to share value.
"""
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_TRANSIENT = "[TRANSIENT]"

ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
PRICING_YEARS = 10
FINALITY_DAYS = 3  # reanalysis data needs a few days to stabilise
VOID_AFTER_DAYS = 45  # unsettleable policies can be voided (premium refunded)
MAX_WINDOW_DAYS = 31
MAX_PREMIUM_RATIO_BPS = 9000  # refuse cover that is (almost) certain to pay
VALUE_TOLERANCE_X10 = 5  # 0.5 mm / 0.5 degC / 0.5 km/h absolute ...
VALUE_TOLERANCE_BPS = 300  # ... or 3% of the threshold, whichever is larger

# metric -> (Open-Meteo daily variable, aggregation over the window, unit)
METRICS = {
    "rain_total": ("precipitation_sum", "sum", "mm"),
    "rain_max_day": ("precipitation_sum", "max", "mm"),
    "temp_max": ("temperature_2m_max", "max", "degC"),
    "temp_min": ("temperature_2m_min", "min", "degC"),
    "wind_max": ("wind_speed_10m_max", "max", "km/h"),
}


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass


@allow_storage
@dataclass
class Pool:
    creator: Address
    name: str
    loading_bps: u256  # underwriter margin on top of the actuarial rate
    max_policy_bps: u256  # max payout per policy as share of free liquidity
    allow_backdated: bool  # test/demo pools only: windows may start in the past
    balance: u256  # all GEN held for this pool (free + locked)
    locked: u256  # sum of payouts of ACTIVE policies
    total_shares: u256
    premiums_earned: u256
    claims_paid: u256
    policy_count: u256


@allow_storage
@dataclass
class Policy:
    pool_id: u256
    buyer: Address
    lat_e4: i256  # latitude * 10^4
    lon_e4: i256
    start_date: str  # YYYY-MM-DD (UTC days, inclusive)
    end_date: str
    metric: str
    trigger_above: bool  # True: value >= threshold triggers; False: value <= threshold
    threshold_x10: i256  # threshold * 10 in the metric's unit
    payout: u256
    premium: u256
    pricing_json: str  # {"years": n, "hits": h, "history": [...]}
    status: str  # ACTIVE | PAID | EXPIRED | VOID
    observed_x10: i256
    settled_at: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_day(s: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except Exception:
        raise gl.vm.UserError(f"{ERROR_EXPECTED} dates must be YYYY-MM-DD")


def _shift_year(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb in a non-leap year
        return d.replace(year=d.year + years, day=28)


def _coord(v_e4: int) -> str:
    sign = "-" if v_e4 < 0 else ""
    a = abs(v_e4)
    return f"{sign}{a // 10000}.{a % 10000:04d}"


def _archive_url(lat_e4: int, lon_e4: int, var: str, start: date, end: date) -> str:
    return (
        f"{ARCHIVE_API}?latitude={_coord(lat_e4)}&longitude={_coord(lon_e4)}"
        f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
        f"&daily={var}&timezone=UTC"
    )


def _fetch_daily(url: str, var: str) -> dict:
    """Return {YYYY-MM-DD: float|None} from an Open-Meteo daily response."""
    try:
        resp = gl.nondet.web.get(url)
    except Exception:
        raise gl.vm.UserError(f"{ERROR_TRANSIENT} weather API unreachable")
    status = getattr(resp, "status", None) or getattr(resp, "status_code", 200)
    if 400 <= status < 500:
        raise gl.vm.UserError(f"{ERROR_EXTERNAL} weather API returned {status}")
    if status >= 500:
        raise gl.vm.UserError(f"{ERROR_TRANSIENT} weather API returned {status}")
    try:
        data = json.loads(resp.body.decode("utf-8"))
        days = data["daily"]["time"]
        vals = data["daily"][var]
    except Exception:
        raise gl.vm.UserError(f"{ERROR_TRANSIENT} malformed weather API response")
    return {str(d): (None if v is None else float(v)) for d, v in zip(days, vals)}


def _aggregate_x10(series: dict, start: date, end: date, agg: str):
    """Aggregate the window from a daily series; None if any day is missing."""
    vals = []
    d = start
    while d <= end:
        v = series.get(d.isoformat())
        if v is None:
            return None
        vals.append(v)
        d += timedelta(days=1)
    if agg == "sum":
        out = sum(vals)
    elif agg == "max":
        out = max(vals)
    else:
        out = min(vals)
    return int(round(out * 10))


def _triggered(value_x10: int, threshold_x10: int, above: bool) -> bool:
    return value_x10 >= threshold_x10 if above else value_x10 <= threshold_x10


def _premium(payout: int, years: int, hits: int, loading_bps: int) -> int:
    # Laplace-smoothed trigger frequency, so a clean history never prices at 0.
    return payout * (2 * hits + 1) * (10000 + loading_bps) // (2 * (years + 1) * 10000)


def _tolerance_x10(threshold_x10: int) -> int:
    return max(VALUE_TOLERANCE_X10, abs(threshold_x10) * VALUE_TOLERANCE_BPS // 10000)


class ParametricWeatherCover(gl.Contract):
    pools: TreeMap[u256, Pool]
    policies: TreeMap[u256, Policy]
    shares: TreeMap[str, u256]  # f"{pool_id}:{holder_hex}"
    pool_count: u256
    policy_count: u256

    def __init__(self):
        self.pool_count = u256(0)
        self.policy_count = u256(0)

    # ------------------------------------------------------------ underwriting

    @gl.public.write
    def create_pool(self, name: str, loading_bps: int, max_policy_bps: int, allow_backdated: bool) -> int:
        name = name.strip()
        if not name or len(name) > 100:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} name must be 1-100 chars")
        if not (0 <= loading_bps <= 20000):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} loading_bps must be 0-20000")
        if not (100 <= max_policy_bps <= 10000):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} max_policy_bps must be 100-10000")
        pid = self.pool_count
        self.pools[pid] = Pool(
            creator=gl.message.sender_address,
            name=name,
            loading_bps=u256(loading_bps),
            max_policy_bps=u256(max_policy_bps),
            allow_backdated=bool(allow_backdated),
            balance=u256(0),
            locked=u256(0),
            total_shares=u256(0),
            premiums_earned=u256(0),
            claims_paid=u256(0),
            policy_count=u256(0),
        )
        self.pool_count = u256(int(pid) + 1)
        return int(pid)

    @gl.public.write.payable
    def deposit(self, pool_id: int) -> int:
        p = self._pool(pool_id)
        amount = int(gl.message.value)
        if amount <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} attach GEN to deposit")
        bal, total = int(p.balance), int(p.total_shares)
        minted = amount if total == 0 or bal == 0 else amount * total // bal
        if minted <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} deposit too small")
        key = f"{pool_id}:{gl.message.sender_address.as_hex}"
        self.shares[key] = u256(int(self.shares.get(key, u256(0))) + minted)
        p.total_shares = u256(total + minted)
        p.balance = u256(bal + amount)
        return minted

    @gl.public.write
    def withdraw(self, pool_id: int, share_amount: int) -> int:
        p = self._pool(pool_id)
        key = f"{pool_id}:{gl.message.sender_address.as_hex}"
        held = int(self.shares.get(key, u256(0)))
        if share_amount <= 0 or share_amount > held:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} not enough shares")
        bal, total = int(p.balance), int(p.total_shares)
        amount = share_amount * bal // total
        if amount > bal - int(p.locked):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} liquidity is locked by active policies")
        self.shares[key] = u256(held - share_amount)
        p.total_shares = u256(total - share_amount)
        p.balance = u256(bal - amount)
        if amount > 0:
            _Payee(gl.message.sender_address).emit_transfer(value=u256(amount))
        return amount

    # ---------------------------------------------------------------- policies

    @gl.public.write.payable
    def buy_policy(
        self,
        pool_id: int,
        lat_e4: int,
        lon_e4: int,
        start_date: str,
        end_date: str,
        metric: str,
        trigger_above: bool,
        threshold_x10: int,
        payout: int,
    ) -> dict:
        """Buy cover. Attach the maximum premium you accept; the excess is refunded."""
        p = self._pool(pool_id)
        if metric not in METRICS:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} metric must be one of {sorted(METRICS)}")
        if not (-900000 <= lat_e4 <= 900000) or not (-1800000 <= lon_e4 <= 1800000):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} coordinates out of range")
        start, end = _parse_day(start_date), _parse_day(end_date)
        days = (end - start).days + 1
        if not (1 <= days <= MAX_WINDOW_DAYS):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} window must be 1-{MAX_WINDOW_DAYS} days")
        today = _now().date()
        if start <= today and not p.allow_backdated:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} window must start after today (UTC)")
        if start > today + timedelta(days=366):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} window starts too far ahead")
        if not (-1000 <= threshold_x10 <= 50000):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} threshold out of range")
        free = int(p.balance) - int(p.locked)
        if payout <= 0 or payout * 10000 > free * int(p.max_policy_bps):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} payout exceeds pool capacity")

        var, agg, _unit = METRICS[metric]
        above = bool(trigger_above)

        def price() -> dict:
            first = _shift_year(start, -PRICING_YEARS)
            last = _shift_year(end, -1)
            series = _fetch_daily(_archive_url(lat_e4, lon_e4, var, first, last), var)
            history = []
            for k in range(PRICING_YEARS, 0, -1):
                s, e = _shift_year(start, -k), _shift_year(end, -k)
                v = _aggregate_x10(series, s, e, agg)
                if v is not None:
                    history.append([s.year, v])
            if len(history) < PRICING_YEARS - 2:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} not enough weather history for this location")
            hits = sum(1 for _, v in history if _triggered(v, threshold_x10, above))
            return {"years": len(history), "hits": hits, "history": history}

        def validate(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_leader_error(leaders_res, price)
            theirs = leaders_res.calldata
            hist = theirs.get("history", [])
            if int(theirs["years"]) != len(hist):
                return False
            if int(theirs["hits"]) != sum(1 for _, v in hist if _triggered(int(v), threshold_x10, above)):
                return False  # leader's hit count must follow from its own history
            mine = price()
            return mine["years"] == int(theirs["years"]) and abs(mine["hits"] - int(theirs["hits"])) <= 1

        quote = gl.vm.run_nondet_unsafe(price, validate)
        years, hits = int(quote["years"]), int(quote["hits"])
        premium = _premium(payout, years, hits, int(p.loading_bps))
        if premium * 10000 >= payout * MAX_PREMIUM_RATIO_BPS:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} uninsurable: triggered in {hits}/{years} past years")
        paid = int(gl.message.value)
        if paid < premium:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} premium is {premium} wei, attached {paid}")

        pol_id = self.policy_count
        self.policies[pol_id] = Policy(
            pool_id=u256(pool_id),
            buyer=gl.message.sender_address,
            lat_e4=i256(lat_e4),
            lon_e4=i256(lon_e4),
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            metric=metric,
            trigger_above=above,
            threshold_x10=i256(threshold_x10),
            payout=u256(payout),
            premium=u256(premium),
            pricing_json=json.dumps(quote, sort_keys=True),
            status="ACTIVE",
            observed_x10=i256(0),
            settled_at="",
        )
        self.policy_count = u256(int(pol_id) + 1)
        p.balance = u256(int(p.balance) + premium)
        p.locked = u256(int(p.locked) + payout)
        p.premiums_earned = u256(int(p.premiums_earned) + premium)
        p.policy_count = u256(int(p.policy_count) + 1)
        if paid > premium:
            _Payee(gl.message.sender_address).emit_transfer(value=u256(paid - premium))
        return {"policy_id": int(pol_id), "premium": str(premium), "hits": hits, "years": years}

    @gl.public.write
    def settle(self, policy_id: int) -> dict:
        pol = self._policy(policy_id)
        if pol.status != "ACTIVE":
            raise gl.vm.UserError(f"{ERROR_EXPECTED} policy already settled")
        start, end = _parse_day(pol.start_date), _parse_day(pol.end_date)
        if _now().date() < end + timedelta(days=FINALITY_DAYS):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} data not final until {(end + timedelta(days=FINALITY_DAYS)).isoformat()}")

        lat, lon, metric = int(pol.lat_e4), int(pol.lon_e4), pol.metric
        threshold, above = int(pol.threshold_x10), bool(pol.trigger_above)
        var, agg, _unit = METRICS[metric]
        tol = _tolerance_x10(threshold)

        def observe() -> dict:
            series = _fetch_daily(_archive_url(lat, lon, var, start, end), var)
            v = _aggregate_x10(series, start, end, agg)
            if v is None:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} weather data incomplete for window")
            return {"value_x10": v, "triggered": _triggered(v, threshold, above)}

        def validate(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_leader_error(leaders_res, observe)
            theirs = leaders_res.calldata
            lv = int(theirs["value_x10"])
            if bool(theirs["triggered"]) != _triggered(lv, threshold, above):
                return False  # verdict must follow from the leader's own value
            mine = observe()
            if mine["triggered"] != bool(theirs["triggered"]):
                return False
            return abs(mine["value_x10"] - lv) <= tol

        obs = gl.vm.run_nondet_unsafe(observe, validate)

        p = self._pool(int(pol.pool_id))
        payout = int(pol.payout)
        p.locked = u256(int(p.locked) - payout)
        pol.observed_x10 = i256(int(obs["value_x10"]))
        pol.settled_at = _now().isoformat()
        if obs["triggered"]:
            pol.status = "PAID"
            p.balance = u256(int(p.balance) - payout)
            p.claims_paid = u256(int(p.claims_paid) + payout)
            _Payee(pol.buyer).emit_transfer(value=u256(payout))
        else:
            pol.status = "EXPIRED"
        return {"status": pol.status, "observed_x10": int(obs["value_x10"]), "threshold_x10": threshold}

    @gl.public.write
    def void(self, policy_id: int) -> None:
        """If no data ever arrives, refund the premium and release the lock."""
        pol = self._policy(policy_id)
        if pol.status != "ACTIVE":
            raise gl.vm.UserError(f"{ERROR_EXPECTED} policy already settled")
        if _now().date() <= _parse_day(pol.end_date) + timedelta(days=VOID_AFTER_DAYS):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} too early to void")
        p = self._pool(int(pol.pool_id))
        premium = int(pol.premium)
        p.locked = u256(int(p.locked) - int(pol.payout))
        p.balance = u256(int(p.balance) - premium)
        p.premiums_earned = u256(int(p.premiums_earned) - premium)
        pol.status = "VOID"
        pol.settled_at = _now().isoformat()
        _Payee(pol.buyer).emit_transfer(value=u256(premium))

    # -------------------------------------------------------------------- views

    @gl.public.view
    def get_pool(self, pool_id: int) -> dict:
        p = self._pool(pool_id)
        return {
            "id": pool_id,
            "creator": p.creator.as_hex,
            "name": p.name,
            "loading_bps": int(p.loading_bps),
            "max_policy_bps": int(p.max_policy_bps),
            "allow_backdated": bool(p.allow_backdated),
            "balance": str(int(p.balance)),
            "locked": str(int(p.locked)),
            "free": str(int(p.balance) - int(p.locked)),
            "total_shares": str(int(p.total_shares)),
            "premiums_earned": str(int(p.premiums_earned)),
            "claims_paid": str(int(p.claims_paid)),
            "policy_count": int(p.policy_count),
        }

    @gl.public.view
    def get_shares(self, pool_id: int, holder: str) -> str:
        return str(int(self.shares.get(f"{pool_id}:{Address(holder).as_hex}", u256(0))))

    @gl.public.view
    def get_policy(self, policy_id: int) -> dict:
        pol = self._policy(policy_id)
        _var, _agg, unit = METRICS[pol.metric]
        return {
            "id": policy_id,
            "pool_id": int(pol.pool_id),
            "buyer": pol.buyer.as_hex,
            "lat": _coord(int(pol.lat_e4)),
            "lon": _coord(int(pol.lon_e4)),
            "start_date": pol.start_date,
            "end_date": pol.end_date,
            "metric": pol.metric,
            "unit": unit,
            "trigger": (">=" if pol.trigger_above else "<=") + f" {int(pol.threshold_x10) / 10}",
            "threshold_x10": int(pol.threshold_x10),
            "payout": str(int(pol.payout)),
            "premium": str(int(pol.premium)),
            "pricing": json.loads(pol.pricing_json),
            "status": pol.status,
            "observed_x10": int(pol.observed_x10),
            "settled_at": pol.settled_at,
        }

    @gl.public.view
    def get_counts(self) -> dict:
        return {"pools": int(self.pool_count), "policies": int(self.policy_count)}

    # ------------------------------------------------------------------ helpers

    def _pool(self, pool_id: int) -> Pool:
        pid = u256(pool_id)
        if pid not in self.pools:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} unknown pool")
        return self.pools[pid]

    def _policy(self, policy_id: int) -> Policy:
        pid = u256(policy_id)
        if pid not in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} unknown policy")
        return self.policies[pid]


def _handle_leader_error(leaders_res, leader_fn) -> bool:
    leader_msg = getattr(leaders_res, "message", "")
    try:
        leader_fn()
        return False
    except gl.vm.UserError as e:
        msg = getattr(e, "message", str(e))
        if msg.startswith(ERROR_EXPECTED) or msg.startswith(ERROR_EXTERNAL):
            return msg == leader_msg
        if msg.startswith(ERROR_TRANSIENT) and leader_msg.startswith(ERROR_TRANSIENT):
            return True
        return False
    except Exception:
        return False
