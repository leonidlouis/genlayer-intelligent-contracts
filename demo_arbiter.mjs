import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
// Usage: node demo_arbiter.mjs <EvidenceArbiter address>
//        node demo_arbiter.mjs <address> <agreement id>   (resume the dispute steps of an existing agreement)
// Payer = deployer wallet (.wallet). Payee = a throwaway Studionet account kept in ./.demo-payee (git-ignored).
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const payerAcct = createAccount(privateKey);
const PAYEE_FILE = new URL("./.demo-payee", import.meta.url);
if (!existsSync(PAYEE_FILE)) writeFileSync(PAYEE_FILE, JSON.stringify({ privateKey: generatePrivateKey() }), { mode: 0o600 });
const payeeAcct = createAccount(JSON.parse(readFileSync(PAYEE_FILE, "utf8")).privateKey);
const payer = createClient({ chain: studionet, account: payerAcct });
const payee = createClient({ chain: studionet, account: payeeAcct });
const address = process.argv[2];
const GEN = 10n ** 18n;
const RAW = "https://raw.githubusercontent.com/leonidlouis/genlayer-intelligent-contracts/main/examples/evidence-arbiter-demo";
const show = (x) => JSON.stringify(x, (k, v) => typeof v === "bigint" ? v.toString() : v instanceof Map ? Object.fromEntries(v) : v, 1);
const w = async (client, functionName, args, value = 0n) => {
  const hash = await client.writeContract({ address, functionName, args, value });
  let r;
  for (let i = 0; ; i++) {  // tolerate transient RPC hiccups while polling
    try { r = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, interval: 5000, retries: 240 }); break; }
    catch (e) { if (i >= 5) throw e; console.log("  (rpc error while waiting, retrying)", e.shortMessage ?? e.message); await new Promise((s) => setTimeout(s, 10000)); }
  }
  const lr = r?.consensus_data?.leader_receipt?.[0] ?? r?.consensus_data?.leader_receipt;
  const votes = Object.values(r?.consensus_data?.votes ?? {}).filter((v) => v !== "idle");
  console.log(functionName, hash, "->", r.statusName ?? r.status, r.txExecutionResultName ?? r.result_name ?? r.resultName ?? r.result,
    "| leader:", lr?.execution_result ?? "", "| votes:", votes.join(","));
  if ((lr?.execution_result ?? "SUCCESS") !== "SUCCESS") throw new Error(`${functionName} failed: ${show(lr?.result ?? lr)}`.slice(0, 2000));
  return r;
};
const r = (functionName, args = []) => payer.readContract({ address, functionName, args });
console.log("payer", payerAcct.address, "payee (throwaway)", payeeAcct.address);

const TERMS = `The payee writes the README for the open-source "tidepool" CLI and delivers it as a public URL by 2026-11-01.
The README must contain four sections: (1) Installation, (2) Usage with at least 3 command examples,
(3) API reference covering every public function, (4) License.
Payment: 100% if all four sections are present. Each missing section reduces the payment by 25 percentage points.
Sections may not be dropped or postponed without a written amendment to these terms.`;

let id = process.argv[3] === undefined ? undefined : Number(process.argv[3]);
const fresh = id === undefined;
if (fresh) {
await w(payer, "propose", [payeeAcct.address, "tidepool README", TERMS, 1800, 1800], 4n * GEN);
id = Number(await r("get_agreement_count")) - 1;
await w(payee, "accept", [id]);
await w(payer, "dispute", [id, "The delivered README has no API reference section, which the terms require. I should not pay the full amount."]);
await w(payer, "submit_evidence", [id, `${RAW}/tidepool-README.md`, "The README as delivered"]);
await w(payee, "state_position", [id, "I delivered a complete README for CLI users. The API reference was left out on purpose because function names are still changing."]);
await w(payee, "submit_evidence", [id, `${RAW}/delivery-note.md`, "My delivery note"]);
}
console.log("agreement id", id);
await w(payer, "ready", [id]);
await w(payee, "ready", [id]);
await w(payer, "rule", [id]);
let a = await r("get_agreement", [id]);
console.log("first ruling", show(a.get?.("rulings") ?? a.rulings));

// Bonded appeal by whichever party received less, then the final appeal ruling.
const pct = Number((a.get?.("rulings") ?? a.rulings)[0].get?.("payee_pct") ?? (a.get?.("rulings") ?? a.rulings)[0].payee_pct);
const appellant = pct < 50 ? payee : payer;
const bond = 4n * GEN / 10n;
await w(appellant, "appeal", [id, pct < 50
  ? "The ruling ignored that the README is complete for CLI users; the API reference was a reasonable omission."
  : "The README also lacks any description of configuration options, so the payment should be lower."], bond);
await w(payer, "ready", [id]);
await w(payee, "ready", [id]);
await w(payer, "rule", [id]);
a = await r("get_agreement", [id]);
console.log("final agreement", show(a));
