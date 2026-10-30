import { readFileSync } from "node:fs";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";
const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const client = createClient({ chain: studionet, account: createAccount(privateKey) });
// Usage: node demo_oracle.mjs <SourceQuorumOracle address>
const address = process.argv[2];
const w = async (functionName, args, value = 0n) => {
  const hash = await client.writeContract({ address, functionName, args, value });
  const r = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, interval: 5000, retries: 150 });
  console.log(functionName, hash, "->", r.txExecutionResultName ?? r.result_name ?? r.resultName ?? r.result);
  return r;
};
await w("ask", [
  "Has Python 3.14.0 been released as a final (stable) version?",
  "YES if the source shows that Python 3.14.0 (or the 3.14 release cycle) had its final/stable release on or before today. NO if it shows 3.14.0 is still unreleased or only a pre-release (alpha/beta/rc).",
  ["https://endoflife.date/api/python.json",
   "https://www.python.org/downloads/release/python-3140/",
   "https://peps.python.org/pep-0745/"],
  2, 0, 86400], 1000000000000000n);
const n = await client.readContract({ address, functionName: "get_claim_count", args: [] });
console.log("claim count", n);
await w("resolve", [Number(n) - 1]);
const c = await client.readContract({ address, functionName: "get_claim", args: [Number(n) - 1] });
console.log(JSON.stringify(c, (k, v) => typeof v === "bigint" ? v.toString() : v instanceof Map ? Object.fromEntries(v) : v, 1));
