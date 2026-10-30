// Usage: node deploy.mjs <contract.py>
// Deploys to Studionet. Reads the deployer key from ./.wallet ({"privateKey":"0x..."}), which is git-ignored.
import { readFileSync, appendFileSync } from "node:fs";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const { privateKey } = JSON.parse(readFileSync(new URL("./.wallet", import.meta.url), "utf8"));
const account = createAccount(privateKey);
const client = createClient({ chain: studionet, account });
const file = process.argv[2];
const code = readFileSync(file, "utf8");
const schema = await client.getContractSchemaForCode(code);
console.log("schema ok, methods:", Object.keys(schema.methods || {}).join(", "));
const hash = await client.deployContract({ code, args: [] });
console.log("deploy tx", hash);
const r = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, interval: 5000, retries: 120 });
const addr = r?.data?.contract_address || r?.txDataDecoded?.contractAddress || r?.recipient;
console.log("status", r.statusName ?? r.status, "result", r.txExecutionResultName ?? r.result_name ?? "", "address", addr);
appendFileSync("deployments.jsonl", JSON.stringify({ file, network: "studionet", tx: hash, address: addr, at: new Date().toISOString() }) + "\n");
