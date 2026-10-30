# GenLayer Intelligent Contracts (Points S2 – Builder)

Deployed on **Studionet** (chain 61999) from 0x3E45f4E55Ce1d0FA5a4aF45EC8B33Cfc4dB23C85.

| Contract | Address | Evidence |
|---|---|---|
| RubricBounty (`contracts/rubric_bounty.py`) | 0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3 | https://studio.genlayer.com/?import-contract=0xa387cE7ae77ceC30fADBf648A08Cbc8E7B8f7ff3 |
| SourceQuorumOracle (`contracts/source_quorum_oracle.py`) | 0x9AaaC4C9118E184A01Cb29FAc0f86A6f99DAB787 | https://studio.genlayer.com/?import-contract=0x9AaaC4C9118E184A01Cb29FAc0f86A6f99DAB787 |

## RubricBounty
Escrowed GEN bounties judged against a weighted rubric. The poster funds `create_bounty` (up to 8 weighted criteria, pass threshold, deadline).
Hunters `submit` an https URL (max 3 attempts each). `judge` fetches the page; the LLM grades each criterion 0-10 and code computes a
weighted 0-100 score. Validators re-grade independently and must agree on pass/fail, find the leader's verdict consistent with the leader's
score, and land within ±10 points. The first passing submission is paid automatically; `reclaim` refunds after the deadline.
Submissions are wrapped as untrusted data to resist prompt injection.

## SourceQuorumOracle
A yes/no claim oracle that settles only when several independent sources agree. `ask` takes a question, criteria, 1-5 https sources,
`min_agree`, `not_before` and a TTL (payable keeper tip). `resolve` judges each source YES/NO/UNCLEAR with a supporting quote. It settles only
if at least `min_agree` sources agree and form a majority; otherwise it stays PENDING with a 1h retry cooldown. Validators must reach the
same outcome with at most one per-source verdict mismatch. The resolver earns the tip; `expire` marks the claim INVALID and refunds it after the TTL.
`get_outcome` is meant for cross-contract reads.

## Dev
`.venv/bin/genvm-lint check contracts/*.py`, `.venv/bin/pytest tests/direct` (12 tests), `node deploy.mjs <file>`.
