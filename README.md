# GenLayer Intelligent Contracts

Two Intelligent Contracts for [GenLayer](https://genlayer.com) that use LLM judgment and live web data, settled by validator consensus (Optimistic Democracy + a custom Equivalence Principle validator).

| Contract | What it does | Studionet address | Open in Studio |
|---|---|---|---|
| [`RubricBounty`](contracts/rubric_bounty.py) | Escrowed bounties paid out when an LLM-graded, weighted rubric score passes | `0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3` | [import](https://studio.genlayer.com/?import-contract=0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3) · [explorer](https://explorer-studio.genlayer.com/address/0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3) |
| [`SourceQuorumOracle`](contracts/source_quorum_oracle.py) | Yes/no oracle that settles only when several independent web sources agree | `0x3603Bf1CA7eBa8c23976B5A069b425BDb2Bf2e23` | [import](https://studio.genlayer.com/?import-contract=0x3603Bf1CA7eBa8c23976B5A069b425BDb2Bf2e23) · [explorer](https://explorer-studio.genlayer.com/address/0x3603Bf1CA7eBa8c23976B5A069b425BDb2Bf2e23) |

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

---

## Running it

Requirements: Python 3.12+ and Node 18+.

```bash
# Python tooling (linter + direct-mode test runner)
python -m venv .venv && .venv/bin/pip install genlayer-test genvm-linter   # tested with genlayer-test 0.29.2
npm install

# Lint / validate both contracts
for f in contracts/*.py; do .venv/bin/genvm-lint check "$f"; done

# Unit tests (direct mode, mocked web + LLM, no network needed)
.venv/bin/pytest tests/direct -q
```

### Deploy and try on Studionet

Create a `.wallet` file, which is git-ignored, containing a test key: `{"privateKey": "0x..."}`. Then run:

```bash
node deploy.mjs contracts/source_quorum_oracle.py           # prints the new address
node demo_oracle.mjs <SourceQuorumOracle address>           # ask + resolve the demo claim
```

To try a contract without any setup, open its **Studio import link** from the table above in [GenLayer Studio](https://studio.genlayer.com) and call its methods from the UI.

## Layout

```
contracts/rubric_bounty.py          RubricBounty
contracts/source_quorum_oracle.py   SourceQuorumOracle
tests/direct/                       direct-mode unit tests (13)
deploy.mjs / demo_oracle.mjs        genlayer-js deploy + demo scripts
deployments.jsonl                   deployment log (Studionet)
```

## License

MIT
