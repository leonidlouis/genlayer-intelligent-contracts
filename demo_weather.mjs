import { readFileSync } from "node:fs";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const client = createClient({ chain: studionet, account: createAccount(privateKey) });
// Usage: node demo_weather.mjs <ParametricWeatherCover address>
// Demo pool opts in to backdated windows so a policy can be priced AND settled in one run.
const address = process.argv[2];
const GEN = 10n ** 18n;
const show = (x) => JSON.stringify(x, (k, v) => typeof v === "bigint" ? v.toString() : v instanceof Map ? Object.fromEntries(v) : v, 1);
const w = async (functionName, args, value = 0n) => {
  const hash = await client.writeContract({ address, functionName, args, value });
  const r = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, interval: 5000, retries: 200 });
  const lr = r?.consensus_data?.leader_receipt?.[0] ?? r?.consensus_data?.leader_receipt;
  console.log(functionName, hash, "->", r.statusName ?? r.status, r.txExecutionResultName ?? r.result_name ?? r.resultName ?? r.result,
    "| leader:", lr?.execution_result ?? "", "| votes:", show(r?.consensus_data?.votes ?? ""));
  return r;
};
const r = (functionName, args = []) => client.readContract({ address, functionName, args });

await w("create_pool", ["Jakarta monsoon demo pool", 1000, 2500, true]);
const pid = Number((await r("get_counts")).get?.("pools") ?? (await r("get_counts")).pools) - 1;
await w("deposit", [pid], 20n * GEN);
// Policy: total rainfall at Jakarta (-6.2, 106.85), 20-28 Oct 2026, >= 50.0 mm pays 2 GEN.
await w("buy_policy", [pid, -62000, 1068500, "2026-10-20", "2026-10-28", "rain_total", true, 500, 2n * GEN], 2n * GEN);
const polId = Number((await r("get_counts")).get?.("policies") ?? (await r("get_counts")).policies) - 1;
console.log("policy after pricing", show(await r("get_policy", [polId])));
await w("settle", [polId]);
console.log("policy after settlement", show(await r("get_policy", [polId])));
console.log("pool", show(await r("get_pool", [pid])));
