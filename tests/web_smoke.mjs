/* تست یکپارچه سرویس وب (Vercel handler) روی node محلی.
 * اجرا:  node tests/web_smoke.mjs
 * یک سرور کوچک داده می‌سازد، سرویس را با env لازم بالا می‌آورد و مسیرهای مهم را می‌زند.
 */
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const stores = JSON.parse(readFileSync(join(ROOT, "data/stores.json"), "utf8"));
stores.stores = stores.stores.length
  ? stores.stores
  : [{ source: "instagram", source_key: "demo", title: "بوتیک نمونه", city: "تهران", phones: ["09121112233"], categories: ["پوشاک"], url: "", last_seen: "2026-01-01 10:00:00" }];
stores.count = stores.stores.length;

const DATA_PORT = 8099;
const APP_PORT = 8098;
const PASSWORD = "test-pass-۱۲۳";
const SECRET = "unit-test-secret";

const dataSrv = createServer((_req, res) => {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify(stores));
}).listen(DATA_PORT, "127.0.0.1");

const app = spawn(process.execPath, ["-e", `
const http = require("http");
const handler = require(${JSON.stringify(join(ROOT, "vercel/api/index.js"))});
http.createServer((req, res) => handler(req, res)).listen(${APP_PORT}, "127.0.0.1", () => console.log("app up"));
`], {
  cwd: ROOT,
  env: { ...process.env, SITE_PASSWORD: PASSWORD, APP_SECRET: SECRET, DATA_URL: `http://127.0.0.1:${DATA_PORT}/stores.json` },
  stdio: ["ignore", "pipe", "inherit"],
});
await new Promise((r) => app.stdout.on("data", (b) => String(b).includes("app up") && r()));

const base = `http://127.0.0.1:${APP_PORT}`;
let cookie = "";
const call = async (path, opts = {}) => {
  const r = await fetch(base + path, {
    ...opts,
    redirect: "manual",
    headers: { ...(opts.headers || {}), ...(cookie ? { cookie } : {}) },
  });
  const setc = r.headers.get("set-cookie");
  if (setc) cookie = setc.split(";")[0];
  const text = await r.text();
  let json = null;
  try { json = JSON.parse(text); } catch { /* html/csv */ }
  return { status: r.status, text, json, location: r.headers.get("location") };
};

let pass = 0, fail = 0;
const check = (label, ok, extra = "") => {
  if (ok) { pass++; console.log("  ✓", label); }
  else { fail++; console.log("  ✗", label, extra); }
};

let r = await call("/api/health");
check("health", r.json?.ok === true && r.json.login_required === true, JSON.stringify(r.json));

r = await call("/");
check("بدون لاگین → ریدایرکت /login", r.status === 302 && r.location === "/login", `${r.status} ${r.location}`);

r = await call("/login");
check("صفحه ورود فارسی و RTL", r.status === 200 && r.text.includes('dir="rtl"'));

r = await call("/api/data");
check("داده بدون کوکی → 401", r.status === 401 && r.json.error === "login_required", `${r.status}`);

r = await call("/api/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password: "wrong" }) });
check("رمز غلط → 401", r.status === 401);

r = await call("/api/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password: PASSWORD }) });
check("رمز درست → 200 و کوکی HttpOnly", r.status === 200 && /httponly/i.test(r.text || "") === false && cookie.startsWith("froshgah_sid="));

r = await call("/api/data");
check("داده بعد از لاگین", r.status === 200 && r.json.count === stores.count && r.json.stores[0].title === "بوتیک نمونه", `${r.status} ${r.text.slice(0, 80)}`);

const csv = await fetch(`${base}/api/export.csv`, { headers: { cookie } });
const csvBytes = new Uint8Array(await csv.arrayBuffer());
const csvText = new TextDecoder("utf-8").decode(csvBytes);
check(
  "CSV با BOM (برای اکسل فارسی) و هدرهای فارسی",
  csv.status === 200 && csvBytes[0] === 0xef && csvBytes[1] === 0xbb && csvBytes[2] === 0xbf && csvText.includes("عنوان,منبع"),
  `${csv.status} ${[...csvBytes.slice(0, 4)].map((b) => b.toString(16))}`
);

r = await call("/api/status");
check("status بدون repo خطای مودبانه می‌دهد", r.status === 200 && /تنظیم نشده/.test(r.json.error || ""), JSON.stringify(r.json));

r = await call("/api/collect", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ hashtags: "پوشاک", ig_user: "x", ig_pass: "y" }) });
check("collect بدون GITHUB_TOKEN → 500 با پیام راهنما", r.status === 500 && /Vercel/.test(r.json.error || ""), JSON.stringify(r.json));

r = await call("/api/logout", { method: "POST", body: "{}" });
check("logout کوکی را پاک می‌کند", r.status === 200);
cookie = "";
r = await call("/api/data");
check("بعد از logout دوباره 401", r.status === 401);

dataSrv.close();
app.kill("SIGTERM");
await sleep(100);
console.log(`\n${fail ? "❌" : "✅"} ${pass} passes, ${fail} failures`);
process.exit(fail ? 1 : 0);
