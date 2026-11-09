import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
// Usage: node demo_sla.mjs <SlaUptimeBond address> [sla id]   (pass an sla id to resume at assessment)
// Provider = deployer wallet (.wallet); customer = throwaway Studionet account in ./.demo-payee (git-ignored).
// Real data: GitHub's public Statuspage feed and github.com as the health endpoint. The period starts
// 2026-10-26 and ends a few minutes after the offer, so live probes and two weeks of real incidents both count.
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
const r = (functionName, args = []) => provider.readContract({ address, functionName, args });
const get = (m, k) => m?.get?.(k) ?? m?.[k];

const SCOPE = `In scope: GitHub core developer services - Git Operations, API Requests, Pull Requests, Issues and Webhooks.
Out of scope: Actions, Pages, Packages, Codespaces, Dependabot, Projects, and every Copilot / AI model service.
An incident counts only if an in-scope service was affected. Errors, failures or unavailability of an in-scope
service = outage. Delays, timeouts for a subset of users, or slowness = degraded. Announced maintenance is excluded.`;

let id = process.argv[3] === undefined ? undefined : Number(process.argv[3]);
if (id === undefined) {
  const start = Math.floor(Date.parse("2026-10-26T00:00:00Z") / 1000);
  const end = Math.floor(Date.now() / 1000) + 6 * 60;
  console.log("provider", providerAcct.address, "customer (throwaway)", customerAcct.address, "period end", new Date(end * 1000).toISOString());
  await w(provider, "offer", [customerAcct.address, "GitHub core (demo)", SCOPE,
    "https://www.githubstatus.com/api/v2/incidents.json", "https://github.com/robots.txt", "User-agent",
    9990, start, end, 60], 4n * GEN);
  id = Number(await r("get_sla_count")) - 1;
  console.log("sla id", id);
  await w(customer, "accept", [id], GEN / 2n);
  await w(customer, "probe", [id]);
  await sleep(65000);
  await w(provider, "probe", [id]);
}
const s = await r("get_sla", [id]);
const opens = Number(get(s, "period_end")) + 300;
console.log("probes", get(s, "probes_total"), "failed", get(s, "probes_failed"), "| assessment opens", new Date(opens * 1000).toISOString());
await sleep(Math.max(0, opens * 1000 - Date.now()) + 45000);
await w(customer, "assess", [id]);
console.log("final", show(await r("get_sla", [id])));
