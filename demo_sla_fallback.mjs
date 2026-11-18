import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
// Usage: node demo_sla_fallback.mjs <SlaUptimeBond address>
// Live test of the bounded fallback: two SLAs whose status feed is a URL that returns HTTP 404 (a provider feed that
// stays broken). The period ends a few minutes after the offer, fallback_grace is the 15-minute minimum.
//   SLA A: probed twice during the period, then assess() fails on the broken feed, then settle_fallback() settles it
//          from the on-chain probe record only.
//   SLA B: never probed; settle_fallback() refunds the fee to the customer and returns the bond to the provider.
// Provider = deployer wallet (.wallet); customer = throwaway Studionet account in ./.demo-payee (git-ignored).
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const PAYEE_FILE = new URL("./.demo-payee", import.meta.url);
if (!existsSync(PAYEE_FILE)) writeFileSync(PAYEE_FILE, JSON.stringify({ privateKey: generatePrivateKey() }), { mode: 0o600 });
const providerAcct = createAccount(privateKey);
const customerAcct = createAccount(JSON.parse(readFileSync(PAYEE_FILE, "utf8")).privateKey);
const provider = createClient({ chain: studionet, account: providerAcct });
const customer = createClient({ chain: studionet, account: customerAcct });
const address = process.argv[2];
const GEN = 10n ** 18n;
const show = (x) => JSON.stringify(x, (k, v) => typeof v === "bigint" ? v.toString() : v instanceof Map ? Object.fromEntries(v) : v, 1);
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));
const w = async (client, functionName, args, value = 0n, allowFail = false) => {
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
  if ((lr?.execution_result ?? "SUCCESS") !== "SUCCESS") {
    const msg = `${functionName} failed: ${show(lr?.result ?? lr)}`.slice(0, 600);
    if (!allowFail) throw new Error(msg);
    console.log("  expected failure:", msg);
  }
  return r;
};
const r = (functionName, args = []) => provider.readContract({ address, functionName, args });
const get = (m, k) => m?.get?.(k) ?? m?.[k];

const SCOPE = `In scope: GitHub core developer services - Git Operations, API Requests, Pull Requests, Issues and Webhooks.
Out of scope: everything else. Errors or unavailability of an in-scope service = outage; slowness = degraded.`;
const BROKEN_FEED = "https://raw.githubusercontent.com/leonidlouis/genlayer-intelligent-contracts/main/does-not-exist/incidents.json";
const start = Math.floor(Date.now() / 1000) - 2 * 3600;
const end = Math.floor(Date.now() / 1000) + 4 * 60;
console.log("provider", providerAcct.address, "customer (throwaway)", customerAcct.address, "period end", new Date(end * 1000).toISOString());
const ids = [];
for (const name of ["GitHub core (fallback demo A, probed)", "GitHub core (fallback demo B, no probes)"]) {
  await w(provider, "offer", [customerAcct.address, name, SCOPE, BROKEN_FEED, "https://github.com/robots.txt", "User-agent",
    9990, start, end, 60, 900], GEN);
  const id = Number(await r("get_sla_count")) - 1;
  ids.push(id);
  await w(customer, "accept", [id], GEN / 5n);
}
const [A, B] = ids;
console.log("sla ids", ids);
await w(customer, "probe", [A]);
await sleep(65000);
if (Date.now() / 1000 < end - 20) await w(provider, "probe", [A]);
const s = await r("get_sla", [A]);
const assessAt = Number(get(s, "period_end")) + 300;
const fallbackAt = Number(get(s, "fallback_opens"));
console.log("A probes", get(s, "probes_total"), "failed", get(s, "probes_failed"), "| assess opens", new Date(assessAt * 1000).toISOString(),
  "| fallback opens", new Date(fallbackAt * 1000).toISOString());
await sleep(Math.max(0, assessAt * 1000 - Date.now()) + 30000);
await w(customer, "assess", [A], 0n, true); // the provider's feed is broken: this must not settle
console.log("A status after failed assess:", get(await r("get_sla", [A]), "status"));
await sleep(Math.max(0, fallbackAt * 1000 - Date.now()) + 30000);
await w(customer, "settle_fallback", [A]);
await w(customer, "settle_fallback", [B]);
console.log("final A", show(await r("get_sla", [A])));
console.log("final B", show(await r("get_sla", [B])));
