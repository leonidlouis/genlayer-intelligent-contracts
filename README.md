# GenLayer Intelligent Contracts

Eight Intelligent Contracts for [GenLayer](https://genlayer.com) that use LLM judgment and live web data, settled by validator consensus (Optimistic Democracy + a custom Equivalence Principle validator).

| Contract | What it does | Studionet address | Open in Studio |
|---|---|---|---|
| [`RubricBounty`](contracts/rubric_bounty.py) | Escrowed bounties paid out when an LLM-graded, weighted rubric score passes | `0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3` | [import](https://studio.genlayer.com/?import-contract=0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3) · [explorer](https://explorer-studio.genlayer.com/address/0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3) |
| [`SourceQuorumOracle`](contracts/source_quorum_oracle.py) | Yes/no oracle that settles only when several independent web sources agree | `0x3603Bf1CA7eBa8c23976B5A069b425BDb2Bf2e23` | [import](https://studio.genlayer.com/?import-contract=0x3603Bf1CA7eBa8c23976B5A069b425BDb2Bf2e23) · [explorer](https://explorer-studio.genlayer.com/address/0x3603Bf1CA7eBa8c23976B5A069b425BDb2Bf2e23) |
| [`ParametricWeatherCover`](contracts/parametric_weather_cover.py) | Parametric weather insurance: underwriter pool, premiums priced from 10 years of weather history, payouts settled from observed weather data | `0x2db617aE09422C072cfd0447030c70fac413ac63` | [import](https://studio.genlayer.com/?import-contract=0x2db617aE09422C072cfd0447030c70fac413ac63) · [explorer](https://explorer-studio.genlayer.com/address/0x2db617aE09422C072cfd0447030c70fac413ac63) |
| [`EvidenceArbiter`](contracts/evidence_arbiter.py) | Two-party escrow with an evidence-based AI arbitration ruling, a percentage split and one bonded appeal | `0x53DeD71da1B8F3Ef1CF33711ACC727A4ACb1d9b0` | [import](https://studio.genlayer.com/?import-contract=0x53DeD71da1B8F3Ef1CF33711ACC727A4ACb1d9b0) · [explorer](https://explorer-studio.genlayer.com/address/0x53DeD71da1B8F3Ef1CF33711ACC727A4ACb1d9b0) |
| [`RetroImpactPool`](contracts/retro_impact_pool.py) | Retroactive funding for an open-source repo: the pool is split between authors of merged PRs by LLM-judged impact against the funder's priorities, with GitHub-to-wallet proof links | `0xb2420398F76d0D5A474579843B38F98a75286Dd4` | [import](https://studio.genlayer.com/?import-contract=0xb2420398F76d0D5A474579843B38F98a75286Dd4) · [explorer](https://explorer-studio.genlayer.com/address/0xb2420398F76d0D5A474579843B38F98a75286Dd4) |
| [`SlaUptimeBond`](contracts/sla_uptime_bond.py) | SLA with a provider bond: live health probes plus an LLM reading of the public status feed against the written SLA scope; uptime and service credits computed in code | `0xE400a078e3514Ab0143e7E078fB7d08790C7C07b` | [import](https://studio.genlayer.com/?import-contract=0xE400a078e3514Ab0143e7E078fB7d08790C7C07b) · [explorer](https://explorer-studio.genlayer.com/address/0xE400a078e3514Ab0143e7E078fB7d08790C7C07b) |
| [`ScalarForecastPool`](contracts/scalar_forecast_pool.py) | Staked forecasting on a numeric real-world value (point + 80% interval), resolved from 1-3 web sources by LLM extraction + median/agreement in code, paid by an interval scoring rule | `0xcbbF46daE1d0e07b4cbA58676b8eE1600893d1dE` | [import](https://studio.genlayer.com/?import-contract=0xcbbF46daE1d0e07b4cbA58676b8eE1600893d1dE) · [explorer](https://explorer-studio.genlayer.com/address/0xcbbF46daE1d0e07b4cbA58676b8eE1600893d1dE) |
| [`OriginalWorkRegistry`](contracts/original_work_registry.py) | Registry of original works with licence terms and staked infringement bounties; claims decided from live pages by code-computed shingle overlap + LLM licence judgment | `0x1F444Be29dcDB7De8538Bd93a3d2f8956d351a41` | [import](https://studio.genlayer.com/?import-contract=0x1F444Be29dcDB7De8538Bd93a3d2f8956d351a41) · [explorer](https://explorer-studio.genlayer.com/address/0x1F444Be29dcDB7De8538Bd93a3d2f8956d351a41) |

Network: **GenLayer Studionet** (chain id 61999, RPC `https://studio.genlayer.com/api`). Full deployment log with transaction hashes: [`deployments.jsonl`](deployments.jsonl).

---

## RubricBounty

An on-chain bounty board where payouts are decided by consensus over a written rubric instead of by the poster.

**Flow**
1. `create_bounty(title, description, criteria, pass_threshold, duration_seconds)` (payable). The poster escrows GEN and defines:
   - up to 8 criteria, given as strings or as `{"name", "weight": 1-10}`,
   - a 1-100 pass threshold, and
   - a duration between 1 hour and 90 days.
2. `submit(bounty_id, url)`. A hunter submits an `https://` link to their work. Each hunter gets 3 attempts per bounty.
3. `judge(bounty_id, submission_id)`. The leader fetches the submission and has the LLM grade each criterion 0-10. The contract code, not the LLM, computes the weighted 0-100 score.
4. The first passing submission is paid automatically. After the deadline, the poster can `reclaim` an unclaimed escrow.

**Consensus.** Each validator re-fetches and re-grades the submission independently. A validator agrees with the leader only if:
- the pass/fail verdict is the same,
- the leader's verdict matches the leader's own score, and
- the scores are within ±10 points.

**Safety**
- Submission content is fenced as untrusted data to resist prompt injection.
- The verdict is derived from numeric scores, never from a free-text "passed" flag.
- Per-criterion scores and reasons are stored, so hunters can see why they failed.

**Views:** `get_bounty`, `get_submission`, `get_bounty_count`.

Tip: submit raw-text URLs (for example a raw gist or `raw.githubusercontent.com` link) so the grader sees the work rather than page chrome.

## SourceQuorumOracle

A reusable yes/no claim oracle. It avoids the weak spot of single-URL oracles, where one stale or manipulated page decides the outcome.

**Flow**
1. `ask(question, criteria, sources, min_agree, not_before, ttl_seconds)` (payable). The requester sets:
   - the question and its resolution criteria,
   - 1-5 `https` sources,
   - a quorum (`min_agree`),
   - an earliest resolve time, and
   - a TTL.

   Any attached GEN becomes a keeper tip.
2. `resolve(claim_id)`. Each source is judged **independently** as `YES`, `NO`, or `UNCLEAR`, with a short supporting quote. The claim settles only if at least `min_agree` sources agree and they form a strict majority. Otherwise it stays `PENDING` and can be retried after a 1-hour cooldown. The caller who settles the claim receives the tip.
3. `expire(claim_id)`. After the TTL, an unresolved claim becomes `INVALID` and the tip is refunded to the requester.

**Source handling**
- Pages are fetched as rendered text (`gl.nondet.web.render(mode="text")`), with a raw-HTML fallback.
- Long pages are cut down to a deterministic, query-focused excerpt: the page head plus the lines that match the most question keywords. Facts buried deep in a page still reach the model.
- The prompt asks the model to apply the criteria literally to concrete facts (versions, dates, numbers). It may only answer `UNCLEAR` when the source has no relevant facts.

**Consensus.** Validators re-fetch and re-judge every source. A validator agrees with the leader only if:
- the final outcome is identical,
- the leader's outcome follows from the leader's own per-source verdicts, and
- at most one per-source verdict differs.

**Composability.** Other contracts can read the result synchronously:

```python
gl.get_contract_at(oracle).view().get_outcome(claim_id)  # "YES" | "NO" | "PENDING" | "INVALID"
```

**Views:** `get_outcome`, `get_claim` (includes per-source verdicts and quotes), `get_claim_count`.

**Live demo (Studionet).** Claim #0 on `0x3603…2e23` asked *"Has Python 3.14.0 been released as a final (stable) version?"* with `min_agree = 2` against three sources:
- endoflife.date API
- the python.org release page
- PEP 745

It resolved **YES with 3/3 sources agreeing**, each verdict backed by a quote (for example *"3.14.0 final: Tuesday, 2025-10-07"*).

## ParametricWeatherCover

Parametric weather insurance with no claims adjuster. Underwriters pool GEN liquidity. Buyers cover a location, a date window and a weather trigger, for example *"total rainfall at -6.2, 106.85 from 20 to 28 Oct is at least 50 mm: pay 2 GEN"*. Public weather data decides both the price and the payout, and every validator re-fetches that data.

**Flow**
1. `create_pool(name, loading_bps, max_policy_bps, allow_backdated)` creates a pool. `deposit(pool_id)` (payable) mints pool shares at the current share price. `withdraw(pool_id, shares)` pays out only **free** liquidity, so active policies stay fully collateralised.
2. `buy_policy(pool_id, lat_e4, lon_e4, start_date, end_date, metric, trigger_above, threshold_x10, payout)` (payable; attach the most you are willing to pay, and the excess is refunded).
   - Metrics: `rain_total`, `rain_max_day`, `temp_max`, `temp_min`, `wind_max`. Triggers can be "at or above" or "at or below" (for example frost cover with `temp_min` at or below -10 °C).
   - **Actuarial pricing (non-deterministic).** The leader pulls the same calendar window for each of the previous 10 years from the [Open-Meteo](https://open-meteo.com) ERA5 historical archive and counts the years that would have triggered. The contract then computes the premium in code: `payout × (2·hits + 1) / (2·(years + 1)) × (1 + loading)`. That is a smoothed trigger frequency, so a clean history never prices at zero.
   - Cover that triggered in almost every past year is refused as uninsurable. Each policy's payout is capped at `max_policy_bps` of free liquidity, and the payout is locked in the pool.
3. `settle(policy_id)` can be called by anyone once the window has ended and the data has had 3 days to settle.
   - **Settlement (non-deterministic).** The leader fetches the observed daily series and aggregates the metric (sum, max or min).
   - If the trigger is met, the buyer is paid from the locked payout. Otherwise the lock is released and the premium stays with the underwriters.
   - Missing days (`null`) raise a transient error, so a policy is never settled on partial data.
4. `void(policy_id)` refunds the premium if no data is available 45 days after the window ends.

**Consensus (custom validators)**
- *Pricing:* validators re-fetch the 10-year history. A validator agrees only if:
  - the leader's hit count follows from the leader's own per-year values,
  - the year counts match, and
  - the hit counts differ by at most 1.
- *Settlement:* validators re-fetch the window. A validator agrees only if:
  - the triggered / not-triggered verdict matches,
  - the leader's verdict follows from the leader's own value and the policy threshold, and
  - the values are within max(0.5 units, 3% of the threshold).

**Accounting.** `balance = free + locked`. Premiums raise the share price and paid claims lower it. Per-pool `premiums_earned`, `claims_paid` and `locked` are stored on-chain. The per-year history behind each premium is stored on the policy, so buyers can audit their price.

`allow_backdated` lets windows start in the past. It exists **only for demo and test pools**, because a buyer who already knows the weather could drain the pool. Production pools set it to `false`, which requires windows to start after today (UTC).

**Views:** `get_pool`, `get_policy` (includes the pricing history and the observed value), `get_shares`, `get_counts`.

**Live demo (Studionet, `node demo_weather.mjs 0x2db6…ac63`).** The demo created pool #0 with a 10% loading, deposited 20 GEN and bought policy #0: Jakarta (-6.2, 106.85), total rainfall 2026-10-20 to 2026-10-28 at or above 50 mm, paying 2 GEN.
- *Pricing* ([`0xdecf2b75…7045`](https://explorer-studio.genlayer.com/tx/0xdecf2b754baf594d52c143e470486bdd87e7f30ffaec2ffc91f1016008547045)): the 10-year history (2016-2025) gave 177.8, 35.4, 58.3, 16.4, 64.2, 74.2, 82.3, 26.6, 12.6 and 100.9 mm. That is **6 of 10 years triggered**, for a **premium of 1.3 GEN**. Consensus was reached with validators agreeing.
- *Settlement* ([`0x8b1fb9a6…d35d`](https://explorer-studio.genlayer.com/tx/0x8b1fb9a6d66537fa8c24709df4a7a5756c3dc5e5ecab648b0513018e1c53d35d)): the observed total was **57.1 mm, at or above 50 mm, so the policy was PAID**. The buyer received 2 GEN and the lock was released.
- The pool ended with a 19.3 GEN balance (20 + 1.3 premium − 2 claim). The transaction was finalized.

## EvidenceArbiter

A two-party escrow for freelance and service deals. Disputes go to an evidence-reading AI court instead of a trusted middleman, with one bonded appeal.

**Flow**
1. `propose(payee, title, terms, evidence_window, appeal_window)` (payable): the payer escrows GEN against written terms. The agreement only binds once the payee calls `accept`. Before that, the payer can `cancel`.
2. Happy paths need no AI. The payer can `release` (100% to the payee), or the payee can `refund` (100% to the payer).
3. `dispute(id, statement)`: either party freezes the escrow and opens an evidence window. During the window:
   - both sides can file a position with `state_position`,
   - each side can file up to 3 https evidence links (`submit_evidence`), and
   - each side can mark `ready`.
4. `rule(id)` can be called once both sides are ready or the window has closed.
   - **Ruling (non-deterministic).** The leader fetches every evidence link as rendered text and fences each item as untrusted data, with the delimiters neutralised so evidence cannot close its own fence.
   - The LLM applies the **terms** obligation by obligation and returns the payee's share (0-100%), per-obligation findings and its reasoning.
   - The contract derives the outcome in code: at least 60 is `PAYEE`, at most 40 is `PAYER`, anything else is `SPLIT`.
5. `appeal(id, reason)` (payable, bond = 10% of the escrow).
   - Only the side that received less can appeal (either side on an exact 50/50), and only within the appeal window.
   - A rebuttal round opens. Then `rule` runs again as an appeal panel that sees the first ruling and the appeal reason, and is told not to split the difference by default.
   - The appeal ruling is final and pays out immediately.
   - If it moves the split at least 10 points toward the appellant, the bond is returned. Otherwise the bond goes to the other side.
6. `finalize(id)` pays out an unappealed ruling after its appeal window closes.

**Consensus (custom validator).** Each validator re-fetches the evidence and re-judges the case independently. A validator agrees only if:
- the outcome bucket is the same,
- the leader's outcome follows from the leader's own share, and
- the shares differ by at most 10 points.

**Safety**
- Statements, notes and evidence are all fenced as untrusted data. The model is told to treat injected instructions as a point *against* the party that filed them, and to prefer independent, verifiable facts over a party's own claims.
- Outsiders cannot act on an agreement.
- The amounts are split in code from the final percentage.

**Views:** `get_agreement` (terms, statements, evidence, both rulings with findings, final split), `get_agreement_count`.

**Live demo (Studionet, `node demo_arbiter.mjs 0x53De…d9b0`)**

The setup was agreement #1 with a 4 GEN escrow:
- Terms: a README for the "tidepool" CLI with 4 required sections, each missing section costing 25 points.
- The payee (a throwaway account) delivered [`tidepool-README.md`](examples/evidence-arbiter-demo/tidepool-README.md), which has no API reference, along with a [delivery note](examples/evidence-arbiter-demo/delivery-note.md) asking for full pay.
- The payer disputed, and both sides filed statements and evidence.

What happened:
- *First ruling* ([`0x9ea9ff5b…8521`](https://explorer-studio.genlayer.com/tx/0x9ea9ff5b29b8e92906ecc315686aaa2ef2aaa5e0379a1f2bc948d401ae608521)): **payee 75% (PAYEE)**. The findings marked Installation, Usage (3 examples) and License as met, and the API reference as not met because *"E2 admits omission"*. Consensus was reached with validators agreeing.
- *Appeal:* the payer posted a 0.4 GEN bond, arguing that a missing configuration section should lower the payment further.
- *Appeal ruling* ([`0x84476b65…5cd`](https://explorer-studio.genlayer.com/tx/0x84476b65eb7c9608807ebd2afad8a2f13f46093c3b35456880a92c59b0a615cd)): **75% upheld**, because *"configuration options … not a requirement in the agreed terms"*.
- The escrow was paid out 3 GEN to the payee and 1 GEN to the payer, and the bond went to the payee. Status `SETTLED`, finalized.


## RetroImpactPool

Retroactive public-goods funding for one open-source repository. Nobody applies and the funder does not hand-pick winners: after a merge window closes, the pool is split between the people whose pull requests were actually merged, weighted by how much each PR advanced the funder's written priorities.

**Flow**
1. `create_round(repo, priorities, window_start, window_end, claim_seconds)` (payable). The funder escrows the pool for `owner/name`, a 1-31 day merge window (UTC days) and up to 2000 chars of priorities.
2. `link_github(login, proof_url)`. A contributor binds a GitHub login to their wallet by publishing a file that contains their address in a repository **owned by that login** (`https://raw.githubusercontent.com/<login>/...`). The owner segment is checked in code; the file is read non-deterministically and validators must agree exactly.
3. `allocate(round_id)`, callable by anyone once the window is over.
   - **Data (non-deterministic).** The leader reads the merged PRs from the GitHub search API. Bots are dropped in code; more than 30 PRs is rejected so the set is always complete.
   - **Judgment (non-deterministic).** The LLM rates every PR on a fixed 4-tier scale against the fenced priorities: 0 noise, 1 minor, 2 substantial, 3 major, with a one-line reason.
   - **Money in code.** Tier weights 0/1/3/6 are summed per author and turned into basis-point shares (rounding remainder to the top author). The LLM never outputs an amount. If no PR carries weight, the pool goes straight back to the funder.
4. `claim(round_id, login)` pays a linked author's share to the linked wallet during the claim window. Anyone can trigger it; funds only go to the wallet bound to the login.
5. `sweep(round_id)` returns unclaimed shares (unlinked or idle authors) to the funder after the claim window.

**Consensus (custom validator).** Each validator re-reads the PR list and re-judges every PR independently. A validator agrees only if:
- its PR set and authors are identical to the leader's,
- the leader's shares follow exactly from the leader's own tiers,
- every author's share is within 15 points of its own, and
- the total variation between the two splits is at most 20 points.

**Safety**
- PR titles and descriptions are fenced as untrusted data with the delimiters neutralised; the model is told to ignore instructions and self-praise in them.
- Wallet binding needs write access to a repo owned by the login, so nobody can claim someone else's share.
- Shares, per-PR tiers and reasons are stored on-chain, so every author can see why they got what they got.

**Views:** `get_round` (PRs with tiers and reasons, shares, claims), `get_link`, `get_round_count`.

**Live demo (Studionet, `node demo_retro.mjs 0xb242…6Dd4`).** Round #0: 5 GEN for `genlayerlabs/genlayer-studio`, PRs merged 2026-10-12 to 2026-11-01, priorities = consensus/appeal and state correctness, validator stability, fee accounting and security; release chores and example tweaks worth little.
- *Allocation* ([`0x85be1077…c2d5`](https://explorer-studio.genlayer.com/tx/0x85be10770b753c680b192933c41396fad876fc015204a732c3a318e814adc2d5)): 9 real PRs by 3 authors. #1784 fee appeal-capacity fix, #1792 finalized-storage reads and #1796 consensus accepted-state fix rated **major**; #1797 release bundle **minor**; #1798 example prompt tweak **noise**. Split: **muncleuscles 38.72%, danieljrc888 32.25%, kp2pml30 29.03%**. Validators agreed; finalized.
- *Identity link* ([`0xb6732405…b953`](https://explorer-studio.genlayer.com/tx/0xb6732405a240263dba24be9861f35af3080ed9de1dfc4dc3f9e2db8987d4b953)): `leonidlouis` bound to the deployer wallet via [`examples/retro-impact-demo/genlayer-identity.txt`](examples/retro-impact-demo/genlayer-identity.txt).
- *Sweep* ([`0x49bce1c9…1c38`](https://explorer-studio.genlayer.com/tx/0x49bce1c9643bf23fd9ec0a612b9d74ea156049031c18d70b458d29540d041c38)): none of the three authors linked a wallet within the 10-minute demo claim window, so the full 5 GEN returned to the funder. Round `CLOSED`.
- Round creation: [`0x2e44a6a7…ad69`](https://explorer-studio.genlayer.com/tx/0x2e44a6a78d387912edd9055fed716d71b28db08fc773275bcfc6021647a0ad69).

## SlaUptimeBond

A service-level agreement that pays its own service credits. The provider backs the SLA with a bond; credits are decided from public evidence instead of the provider's goodwill.

**Flow**
1. `offer(customer, service, scope, status_url, health_url, health_expect, target_bps, period_start, period_end, probe_interval)` (payable). The provider posts the bond and the written SLA scope (which components count, what is an outage vs degraded, what is excluded).
2. `accept(id)` (payable). Only the named customer can accept, paying the service fee into escrow. The provider can `cancel` an unaccepted offer.
3. `probe(id)`, callable by anyone during the period, at most once per `probe_interval`.
   - **Non-deterministic.** The leader GETs the health URL: UP if the status is below 400 and the expected text is present. Validators probe independently and must see the same UP/DOWN.
   - Each failed probe counts `probe_interval` of downtime, so a provider cannot hide an outage behind a green status page.
4. `assess(id)`, callable by anyone 5 minutes after the period ends.
   - **Atlassian Statuspage feeds** (`/api/v2/incidents.json`): incident times, components and updates are parsed in code; the LLM only classifies each incident against the fenced scope as `outage`, `degraded`, `maintenance` or `out_of_scope`.
   - **Any other status page**: the LLM extracts the incidents (ISO start/end and class) from the rendered text, and invalid rows are dropped in code.
   - **In code:** intervals are clipped to the period and merged (outage wins over degraded), degraded minutes count 50%, and the larger of reported and probe-measured downtime is used. Uptime in bps then maps to the credit tier by shortfall below target: 0 → 0%, ≤0.5 pt → 10%, ≤4 pt → 25%, ≤9 pt → 50%, beyond → 100% of the bond.
   - Settlement is immediate: the credit goes to the customer, and the rest of the bond plus the fee go to the provider.

**Consensus (custom validators)**
- *Probe:* validators re-probe; agree only on the same UP/DOWN.
- *Assessment:* validators re-read the feed and re-classify independently. A validator agrees only if:
  - the leader's weighted downtime and credit tier follow from the leader's own incident list,
  - the credit tier is identical to its own, and
  - weighted downtime is within max(90 min, 25%).

**Safety**
- Status-page text is fenced as untrusted data; the model is told to classify by what broke for users, not by the provider's own impact label.
- The LLM never outputs minutes or money: timestamps come from the feed (or are parsed and validated in code) and all arithmetic is deterministic.
- The full incident list with classes and reasons is stored in the settlement report.

**Views:** `get_sla` (probes, failed probe times, settlement report), `get_sla_count`, `credit_table`.

**Live demo (Studionet, `node demo_sla.mjs 0xE400…C07b`).** SLA #0: provider = deployer, customer = a throwaway account. Service "GitHub core (demo)": Git Operations, API Requests, Pull Requests, Issues and Webhooks in scope; Actions, Pages, Copilot, Dependabot and others out of scope; target 99.90%. Period 2026-10-26 00:00 UTC to 2026-11-09 03:31 UTC, bond 4 GEN, fee 0.5 GEN. Health endpoint `https://github.com/robots.txt`; status feed `https://www.githubstatus.com/api/v2/incidents.json`.
- Offer [`0x938b0200…6bdc`](https://explorer-studio.genlayer.com/tx/0x938b020054f0bcc53dbdd59f9fe6cb7bf03c4127b161e03f4f255a85ec076bdc), accept [`0xc8bcd248…2d0d`](https://explorer-studio.genlayer.com/tx/0xc8bcd248f413a181e3b5a94a4cc181ccc70371fd46de07a4ad4b78011bf42d0d).
- *Probes* ([`0xf11beca8…5418`](https://explorer-studio.genlayer.com/tx/0xf11beca87c8fe2f693759c75fdc6fc584ac1b939fd9f0d423882c676e6d95418), [`0xe701b3a6…8c01`](https://explorer-studio.genlayer.com/tx/0xe701b3a6acbf778d694b63ea677e30058b40bcfc127d1b0a118bb6f5fc188c01)): both UP, validators agreed.
- *Assessment* ([`0x4d1ab6d1…fe2b`](https://explorer-studio.genlayer.com/tx/0x4d1ab6d1235c090cc89d1b3988162cafbd246d96c489cf281c2e50f37ee1fe2b)): 17 real GitHub incidents overlapped the period. 7 were classed **out of scope** (Copilot, Actions-only, Dependabot), 8 **degraded** (e.g. Git HTTPS slowness on Nov 3, PR/Git/Issues on Nov 4, API timeouts on Nov 8), 2 **outage** (Issues disruption on Oct 30, plus a zero-length backdated entry). Result: 31 outage + 573 degraded minutes = **317 weighted minutes**, **uptime 98.44%** vs 99.90% target, **25% credit**. The customer received 1 GEN; the provider got 3 GEN of bond back plus the 0.5 GEN fee. Validators agreed; finalized.

## ScalarForecastPool

Forecasting on a **number**, not a yes/no question. Forecasters stake GEN on a point estimate plus an 80% interval; the outcome is read from public web sources after the deadline, and the pot is split by a proper interval scoring rule computed in code.

**Flow**
1. `create_round(metric, spec, unit, decimals, sources, deadline, agree_bps, min_sources, scale_bps, resolve_ttl)` (payable, optional subsidy). The creator defines the metric, a binding resolution spec, the fixed-point precision (values are integers × 10^decimals), 1-3 `https://` sources, how far apart sources may be (`agree_bps`), how many must report (`min_sources`), the score scale and how long resolution may take.
2. `forecast(round_id, point, low, high)` (payable stake ≥ 0.001 GEN). One forecast per address before the deadline, with `low ≤ point ≤ high` (the 80% central interval).
3. `resolve(round_id)`, callable by anyone after the deadline (60 s cooldown between attempts).
   - **Data (non-deterministic).** The leader fetches every source (JSON/CSV as-is, HTML rendered to text, long pages cut to a query-focused excerpt).
   - **Judgment (non-deterministic).** The LLM extracts the figure from each fenced source against the spec and quotes it, or says it is not published.
   - **In code.** The number is parsed to fixed point (half-up); a value whose digits do not literally appear in the fetched text is discarded (anti-hallucination). The outcome is the **median** of the reported values, and the round resolves only if at least `min_sources` reported and the spread (max − min) is within `agree_bps` of the median. Otherwise the attempt is recorded (`NO_QUORUM` / `DISAGREE`) and the round stays open.
4. **Payouts in code.** Penalty = interval score (width + 10 × distance outside the 80% interval, Gneiting–Raftery with α = 0.2) + 2 × |point − outcome|, in bps of the outcome, divided by `scale_bps`; quality q = 1/(1 + penalty)². The pot (stakes + subsidy) is split pro rata to stake × q, rounding dust to the creator. Sharp, correct forecasts win; confident misses are punished harder than honest wide intervals.
5. `void(round_id)` after `deadline + resolve_ttl` if the sources never agreed: every stake and the subsidy are refunded.

**Consensus (custom validator).** Each validator re-fetches and re-extracts every source. It agrees only if:
- the leader's per-source list covers exactly the round's sources,
- the leader's status and median follow exactly from the leader's own per-source values,
- its own status is the same, and
- if resolved, its median is within `agree_bps` (min. 1 unit) of the leader's.

**Safety**
- Source text is fenced as untrusted data with the delimiters neutralised; the model is told to ignore instructions and fake values in it.
- The LLM only returns the number *as written*; it never sees stakes or outputs money. Every payout is integer arithmetic.
- Per-source raw values, parsed values and quotes are stored for every attempt.

**Views:** `get_round` (evidence, outcome, payouts), `get_forecast`, `preview_payouts(round_id, outcome)`, `get_round_count`.

**Live demo (Studionet, `node demo_forecast.mjs 0xcbbF…d1dE`).** Round #0: *ECB euro reference rate, USD per EUR, for 2026-11-13*, 4 decimals, sources = ECB Data Portal API (CSV) and Frankfurter (JSON), both required, agreement within 10 bps, score scale 50 bps, 1 GEN subsidy.
- *Round + forecasts* ([`0x71ab9cb7…2561`](https://explorer-studio.genlayer.com/tx/0x71ab9cb7e9c9d8fc5f79a5b503a70d63a7c5d7fb39b4e6a7e5ab34fbbebb2561), [`0x31b18750…36f6`](https://explorer-studio.genlayer.com/tx/0x31b18750afdbcba021a0464200cb37a445b7b241102559e104c507a04c6b36f6), [`0x6317461d…e1a0`](https://explorer-studio.genlayer.com/tx/0x6317461d973bd2da7270ce0dc3c94575c65c6d4ddbcf66f9132e5075e94be1a0)): A staked 1 GEN on 1.1040 [1.1000, 1.1080]; B staked 0.5 GEN on 1.1150 [1.1120, 1.1180].
- *Resolution* ([`0x508e688c…090b`](https://explorer-studio.genlayer.com/tx/0x508e688c73b20a443e3eec8cdc6d36fdb547c6ca14035b3cbd700c65da02090b)): both sources read **1.1052** (ECB CSV row `…,2026-11-13,1.1052,…`; Frankfurter `"USD":1.1052`), spread 0 bps → outcome **11052**. A (inside its interval, 12 units off) scored q ≈ 0.121; B (missed its interval by 68 units) q ≈ 0.003. Payouts from the 2.5 GEN pot: **A 2.468 GEN, B 0.032 GEN**. Validators agreed (3/3); finalized.

## OriginalWorkRegistry

Plagiarism and licence enforcement for written work. Creators register a work with its licence terms and stake a bounty; anyone who finds an unlicensed copy files a bonded claim, and the claim is decided from the live pages.

**Flow**
1. `register_work(title, canonical_url, licence, licensees, bounty, claim_bond, min_overlap_bps)` (payable stake ≥ one bounty). Licence terms are plain words (e.g. CC BY-NC with credit + link); `licensees` are domains allowed to republish. `top_up`, `add_licensee` and `close_work` (refunds the free stake when nothing is pending) manage it.
2. `file_claim(work_id, suspect_url, note)` (payable bond ≥ `claim_bond`). Checked in code:
   - `https://` only; the canonical URL and every licensee domain and subdomain are exempt (the canonical *host* alone is not, since works often live on shared hosts);
   - **duplicate prevention:** the URL is normalised (scheme, `www.`, query, fragment, trailing slash dropped) and each work accepts one claim per normalised URL, ever (`claim_for_url` shows it);
   - the bounty is **reserved** at filing so pending claims can never overdraw the stake; creators cannot report their own work.
3. `adjudicate(claim_id)`, callable by anyone.
   - **Data (non-deterministic).** The leader fetches both pages (rendered text, tags stripped).
   - **In code.** Both texts are tokenised and compared with word 6-gram shingles: *containment* = share of the original's shingles found on the suspect page, plus coverage, longest shared run and the longest matching passages.
   - **Judgment (non-deterministic).** The LLM sees the licence, the overlap numbers, the matched passages and both fenced pages, and classifies the use (`verbatim_copy`, `close_paraphrase`, `quotation`, `licensed_use`, `fair_use`, `unrelated`), says whether the licence's conditions were met, and quotes the copied passages.
   - **Verdict in code.** Quotes are kept only if their words literally occur in *both* pages. **UPHELD** iff the use is a copy or close paraphrase, the licence was not complied with, ≥ 1 quote verifies, and containment ≥ `min_overlap_bps` (half of it for close paraphrase). Otherwise **REJECTED**; **UNAVAILABLE** if the suspect page cannot be fetched.
4. **Money in code.** UPHELD: the reporter gets the bounty plus the bond back. REJECTED: the bond goes to the creator. UNAVAILABLE: the bond is refunded and the URL is freed for a later claim.

**Consensus (custom validator).** Each validator re-fetches both pages, recomputes the overlap and re-judges. It agrees only if:
- the leader's verdict follows from the leader's own category, licence flag, verified quotes and containment,
- its own verdict is identical,
- containment is within 10 points of its own, and
- for UPHELD, every quote the leader relied on occurs in the validator's own copy of both pages.

**Safety**
- Both pages are fenced as untrusted data with the delimiters neutralised; permission claims inside a page count only as real attribution, never as instructions.
- An LLM that over-claims cannot uphold a claim on its own: the overlap threshold and quote verification are deterministic.
- The LLM never outputs money; overlap metrics, verified quotes and the reasoning are stored in the claim report.

**Views:** `get_work`, `get_claim` (report), `claim_for_url`, `get_counts`.

**Live demo (Studionet, `node demo_registry.mjs 0x1F44…1a41`).** Work #0: [`examples/original-work-demo/original-essay.md`](examples/original-work-demo/original-essay.md) registered with its raw GitHub URL as canonical, licence CC BY-NC with credit + link, licensee `asterie.app`, stake 2 GEN, bounty 1 GEN, claim bond 0.1 GEN, threshold 30% ([`0x8fd9bfa6…35d3`](https://explorer-studio.genlayer.com/tx/0x8fd9bfa655f082f2944dcb92508d869705742c7ed596bfbfd66110c0cff035d3)). Two claims were filed against pages served live from jsDelivr ([`0x68b31902…09f8`](https://explorer-studio.genlayer.com/tx/0x68b3190278d2e772bb8ff894d0a81f2f65a38234645170068e3d5c51a46009f8), [`0xa8cb2966…a113`](https://explorer-studio.genlayer.com/tx/0xa8cb29661b41924be93082a5bb084e02a7d84b00c12cd7074ecc24ec2627a113)).
- *Claim #0, content-farm copy* ([`0xacddb6a3…b6b3`](https://explorer-studio.genlayer.com/tx/0xacddb6a310132286d994da4e2d19098e201cd954ae0fb056c904ba6819aeb6b3)): containment **63.8%**, longest shared run 149 words, `verbatim_copy`, licence not complied ("Verbatim commercial copy without credit or canonical link") → **UPHELD**; the reporter received the 1 GEN bounty plus the 0.1 GEN bond. Validators agreed (3/3).
- *Claim #1, newsletter quoting one line with credit* ([`0xb16023f1…7b8d`](https://explorer-studio.genlayer.com/tx/0xb16023f1eca389c39e11e1c963cded006a295359b761afe16e1dcbd7b7c07b8d)): containment **5.2%**, longest run 18 words, `quotation`, licence complied → **REJECTED**; the 0.1 GEN bond went to the creator. Validators agreed (3/3).
- Work after the demo: stake 1 GEN, 2 claims, 1 upheld, nothing reserved.

---

## Running it

Requirements: Python 3.12+ and Node 18+.

```bash
# Python tooling (linter + direct-mode test runner)
python -m venv .venv && .venv/bin/pip install genlayer-test genvm-linter   # tested with genlayer-test 0.29.2
npm install

# Lint / validate all contracts
for f in contracts/*.py; do .venv/bin/genvm-lint check "$f"; done

# Unit tests (direct mode, mocked web + LLM, no network needed)
.venv/bin/pytest tests/direct -q
```

Direct mode downloads a GenVM runner bundle on first use. Newer genvm releases no longer ship `genvm-universal.tar.xz`; if the download 404s, fetch it from v0.2.16 into the cache first:
`curl -L -o ~/.cache/gltest-direct/genvm-universal-v0.2.16.tar.xz https://github.com/genlayerlabs/genvm/releases/download/v0.2.16/genvm-universal.tar.xz`

### Deploy and try on Studionet

Create a `.wallet` file, which is git-ignored, containing a test key: `{"privateKey": "0x..."}`. Then run:

```bash
node deploy.mjs contracts/source_quorum_oracle.py           # prints the new address
node demo_oracle.mjs <SourceQuorumOracle address>           # ask + resolve the demo claim
node demo_weather.mjs <ParametricWeatherCover address>      # pool, priced policy, settlement
node demo_arbiter.mjs <EvidenceArbiter address>             # agreement, dispute, ruling, appeal
node demo_retro.mjs <RetroImpactPool address>                # funded round, allocation, identity link, sweep
node demo_sla.mjs <SlaUptimeBond address>                    # SLA offer, live probes, status-feed assessment
node demo_forecast.mjs <ScalarForecastPool address>          # numeric round, two forecasts, web resolution + scoring
node demo_registry.mjs <OriginalWorkRegistry address>        # registered work, two infringement claims adjudicated
```

To try a contract without any setup, open its **Studio import link** from the table above in [GenLayer Studio](https://studio.genlayer.com) and call its methods from the UI.

## Layout

```
contracts/rubric_bounty.py          RubricBounty
contracts/source_quorum_oracle.py   SourceQuorumOracle
contracts/parametric_weather_cover.py  ParametricWeatherCover
contracts/evidence_arbiter.py       EvidenceArbiter
contracts/retro_impact_pool.py      RetroImpactPool
contracts/sla_uptime_bond.py        SlaUptimeBond
contracts/scalar_forecast_pool.py   ScalarForecastPool
contracts/original_work_registry.py OriginalWorkRegistry
tests/direct/                       direct-mode unit tests (79)
deploy.mjs / demo_*.mjs             genlayer-js deploy + demo scripts
examples/evidence-arbiter-demo/     evidence files used by the EvidenceArbiter demo
examples/retro-impact-demo/         GitHub identity proof used by the RetroImpactPool demo
examples/original-work-demo/        essay + suspect pages used by the OriginalWorkRegistry demo
deployments.jsonl                   deployment log (Studionet)
```

## License

MIT
