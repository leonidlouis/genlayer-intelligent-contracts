import { readFileSync } from "node:fs";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
// Usage: node demo_retro.mjs <RetroImpactPool address> [round id]   (pass a round id to resume after allocation)
// Funds a retro round for real merged PRs in genlayerlabs/genlayer-studio, allocates it by consensus,
// links a GitHub login with the proof file in examples/retro-impact-demo/, then sweeps unclaimed shares.
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const account = createAccount(privateKey);
const client = createClient({ chain: studionet, account });
const address = process.argv[2];
const GEN = 10n ** 18n;
const PROOF = "https://raw.githubusercontent.com/leonidlouis/genlayer-intelligent-contracts/main/examples/retro-impact-demo/genlayer-identity.txt";
const show = (x) => JSON.stringify(x, (k, v) => typeof v === "bigint" ? v.toString() : v instanceof Map ? Object.fromEntries(v) : v, 1);
const w = async (functionName, args, value = 0n) => {
  const hash = await client.writeContract({ address, functionName, args, value });
  let r;
  for (let i = 0; ; i++) {
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
const r = (functionName, args = []) => client.readContract({ address, functionName, args });

const PRIORITIES = `Fund work that makes GenLayer Studio a reliable place to build and test Intelligent Contracts:
consensus and appeal correctness, state/storage correctness, validator stability, and fee accounting.
Security fixes count fully. Release chores, version bumps and example tweaks are worth little.`;

let id = process.argv[3] === undefined ? undefined : Number(process.argv[3]);
if (id === undefined) {
  await w("create_round", ["genlayerlabs/genlayer-studio", PRIORITIES, "2026-10-12", "2026-11-01", 600], 5n * GEN);
  id = Number(await r("get_round_count")) - 1;
  console.log("round id", id);
  await w("allocate", [id]);
  console.log("allocation", show(await r("get_round", [id])));
  await w("link_github", ["leonidlouis", PROOF]);
  console.log("link", show(await r("get_link", ["leonidlouis"])));
  console.log("waiting for the 10-minute claim window to close...");
  const dl = Number((await r("get_round", [id])).get?.("claim_deadline") ?? (await r("get_round", [id])).claim_deadline);
  await new Promise((s) => setTimeout(s, Math.max(0, dl * 1000 - Date.now()) + 60000));
}
await w("sweep", [id]);
console.log("final round", show(await r("get_round", [id])));
