import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
// Usage: node demo_forecast.mjs <ScalarForecastPool address> [round id]   (pass a round id to resume at resolve)
// Creator + forecaster A = deployer wallet (.wallet); forecaster B = throwaway Studionet account in ./.demo-payee (git-ignored).
// Real data: the ECB euro reference rate (USD per EUR) for a fixing date, read live from the ECB Data Portal API
// and from Frankfurter (which republishes the ECB fixings). Deadline is a few minutes after creation.
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const PAYEE_FILE = new URL("./.demo-payee", import.meta.url);
if (!existsSync(PAYEE_FILE)) writeFileSync(PAYEE_FILE, JSON.stringify({ privateKey: generatePrivateKey() }), { mode: 0o600 });
const aAcct = createAccount(privateKey);
const bAcct = createAccount(JSON.parse(readFileSync(PAYEE_FILE, "utf8")).privateKey);
const A = createClient({ chain: studionet, account: aAcct });
const B = createClient({ chain: studionet, account: bAcct });
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
const r = (functionName, args = []) => A.readContract({ address, functionName, args });
const get = (m, k) => m?.get?.(k) ?? m?.[k];

const DAY = process.env.FIXING_DAY ?? "2026-11-13";
const METRIC = `ECB euro reference exchange rate, US dollars per 1 euro, for ${DAY}`;
const SPEC = `The official ECB euro foreign exchange reference rate for USD (series EXR.D.USD.EUR.SP00.A, published around 14:15 CET)
for the reference date ${DAY}, expressed as US dollars per 1 euro with 4 decimals. Use only the value for exactly that date.`;
const SOURCES = [
  `https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=${DAY}&endPeriod=${DAY}&format=csvdata`,
  `https://api.frankfurter.dev/v1/${DAY}?base=EUR&symbols=USD`,
];

let id = process.argv[3] === undefined ? undefined : Number(process.argv[3]);
if (id === undefined) {
  const deadline = Math.floor(Date.now() / 1000) + 4 * 60;
  console.log("creator/forecaster A", aAcct.address, "forecaster B (throwaway)", bAcct.address, "deadline", new Date(deadline * 1000).toISOString());
  // decimals 4, sources must agree within 10 bps, both required, score scale 50 bps, 1 day to resolve; 1 GEN subsidy
  await w(A, "create_round", [METRIC, SPEC, "USD per EUR", 4, SOURCES, deadline, 10, 2, 50, 86400], GEN);
  id = Number(await r("get_round_count")) - 1;
  console.log("round id", id);
  await w(A, "forecast", [id, 11040, 11000, 11080], GEN);        // A: 1.1040, 80% interval 1.1000-1.1080
  await w(B, "forecast", [id, 11150, 11120, 11180], GEN / 2n);   // B: 1.1150, tighter but higher
}
const rd = await r("get_round", [id]);
const opens = Number(get(rd, "deadline"));
console.log("forecasts", get(rd, "forecasts"), "| resolve opens", new Date(opens * 1000).toISOString());
await sleep(Math.max(0, opens * 1000 - Date.now()) + 30000);
await w(B, "resolve", [id]);
const fin = await r("get_round", [id]);
console.log("final", show(fin));
for (let i = 0; i < Number(get(fin, "forecasts")); i++) console.log("forecast", i, show(await r("get_forecast", [id, i])));
