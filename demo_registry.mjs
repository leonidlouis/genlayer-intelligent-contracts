import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
// Usage: node demo_registry.mjs <OriginalWorkRegistry address>
// Creator = deployer wallet (.wallet); reporter = throwaway Studionet account in ./.demo-payee (git-ignored).
// Registers the essay in examples/original-work-demo/ (canonical URL on raw.githubusercontent.com, CC BY-NC with
// credit + link), then files and adjudicates two real claims against pages served live from a different host
// (jsDelivr, pinned to a commit): an unattributed content-farm copy and a newsletter that quotes one line with credit.
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const PAYEE_FILE = new URL("./.demo-payee", import.meta.url);
if (!existsSync(PAYEE_FILE)) writeFileSync(PAYEE_FILE, JSON.stringify({ privateKey: generatePrivateKey() }), { mode: 0o600 });
const creatorAcct = createAccount(privateKey);
const reporterAcct = createAccount(JSON.parse(readFileSync(PAYEE_FILE, "utf8")).privateKey);
const creator = createClient({ chain: studionet, account: creatorAcct });
const reporter = createClient({ chain: studionet, account: reporterAcct });
const address = process.argv[2];
const GEN = 10n ** 18n;
const show = (x) => JSON.stringify(x, (k, v) => typeof v === "bigint" ? v.toString() : v instanceof Map ? Object.fromEntries(v) : v, 1);
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));
const w = async (client, functionName, args, value = 0n) => {
  const hash = await client.writeContract({ address, functionName, args, value });
  let r;
  for (let i = 0; ; i++) {
    try { r = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, interval: 5000, retries: 240 }); break; }
    catch (e) { if (i >= 5) throw e; console.log("  (rpc error while waiting, retrying)", e.shortMessage ?? e.message); await sleep(10000); }
  }
  const lr = r?.consensus_data?.leader_receipt?.[0] ?? r?.consensus_data?.leader_receipt;
  const votes = Object.values(r?.consensus_data?.votes ?? {}).filter((v) => v !== "idle");
  console.log(functionName, hash, "->", r.statusName ?? r.status, r.txExecutionResultName ?? r.result_name ?? r.resultName ?? r.result,
    "| leader:", lr?.execution_result ?? "", "| votes:", votes.join(","));
  if ((lr?.execution_result ?? "SUCCESS") !== "SUCCESS") throw new Error(`${functionName} failed: ${show(lr?.result ?? lr)}`.slice(0, 2000));
  return r;
};
const r = (functionName, args = []) => creator.readContract({ address, functionName, args });
const get = (m, k) => m?.get?.(k) ?? m?.[k];

const REF = process.env.DEMO_REF ?? "0717a9e";
const CANON = "https://raw.githubusercontent.com/leonidlouis/genlayer-intelligent-contracts/main/examples/original-work-demo/original-essay.md";
const CDN = `https://cdn.jsdelivr.net/gh/leonidlouis/genlayer-intelligent-contracts@${REF}/examples/original-work-demo`;
const LICENCE = `CC BY-NC 4.0. Anyone may copy and republish this essay for NON-COMMERCIAL use only, and only if they credit
the author (Louis Leonid) and link to the canonical copy. Commercial republication, or any republication without credit and
a link, is not permitted. Short quotations with credit for review or commentary are always fine.`;

let wid = process.env.WORK_ID === undefined ? undefined : Number(process.env.WORK_ID);
if (wid === undefined) {
  console.log("creator", creatorAcct.address, "reporter (throwaway)", reporterAcct.address);
  // stake 2 GEN, bounty 1 GEN per upheld claim, claim bond 0.1 GEN, copying needs >= 30% of the original's shingles
  await w(creator, "register_work", ["Night Notes: Why a Journal Works Better in the Dark", CANON, LICENCE, ["asterie.app"],
    GEN, GEN / 10n, 3000], 2n * GEN);
  wid = Number(get(await r("get_counts"), "works")) - 1;
}
console.log("work id", wid);
const claims = [];
for (const [page, note] of [["content-farm-copy.html", "Commercial blog republished most of the essay under a staff byline, no credit or link."],
                            ["attributed-review.html", "Newsletter reuses a line from the essay."]]) {
  await w(reporter, "file_claim", [wid, `${CDN}/${page}`, note], GEN / 10n);
  claims.push(Number(get(await r("get_counts"), "claims")) - 1);
}
console.log("claims", claims);
for (const cid of claims) {
  await w(reporter, "adjudicate", [cid]);
  console.log("claim", cid, show(await r("get_claim", [cid])));
}
console.log("work", show(await r("get_work", [wid])));
