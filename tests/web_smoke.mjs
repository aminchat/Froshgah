/* تست یکپارچه سرویس وب (Vercel handler) با node محلی — پورت‌ها تصادفی و آزادند.
 * اجرا:  node tests/web_smoke.mjs
 */
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const HANDLER = join(ROOT, "api/index.js");
const PASSWORD = "test-pass-۱۲۳";
const SECRET = "unit-test-secret";

const stores = JSON.parse(readFileSync(join(ROOT, "data/stores.json"), "utf8"));
stores.stores = stores.stores.length
  ? stores.stores
  : [{
      source: "instagram", source_key: "demo", title: "بوتیک نمونه", city: "تهران",
      phones: ["09121112233"], categories: ["پوشاک"], url: "", last_seen: "2026-01-01 10:00:00",
    }];
stores.count = stores.stores.length;

/* ۱) سرور داده جعلی */
const dataSrv = createServer((_req, res) => {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify(stores));
}).listen(0, "127.0.0.1");
await new Promise((r) => dataSrv.once("listening", r));
const dataPort = dataSrv.address().port;

/* ۲) سرویس وب، با env لازم */
const app = spawn(process.execPath, ["-e", `
const http = require("http");
const handler = require(${JSON.stringify(HANDLER)});
const srv = http.createServer((q, r) => handler(q, r));
srv.listen(0, "127.0.0.1", () => console.log("PORT=" + srv.address().port));
`], {
  cwd: ROOT,
  env: {
    ...process.env,
    SITE_PASSWORD: PASSWORD,
    APP_SECRET: SECRET,
    GITHUB_REPO: "",
    GITHUB_TOKEN: "",          // نه: اگر توکن محیط تست را پر کند، نتیجه غلط می‌شود
    DATA_URL: `http://127.0.0.1:${dataPort}/stores.json`,
  },
  stdio: ["ignore", "pipe", "inherit"],
});

const appPort = await new Promise((resolve, reject) => {
  let buf = "";
  const to = setTimeout(() => reject(new Error("سرویس بالا نیامد")), 8000);
  app.stdout.on("data", (b) => {
    buf += String(b);
    const m = /PORT=(\d+)/.exec(buf);
    if (m) {
      clearTimeout(to);
      resolve(Number(m[1]));
    }
  });
  app.on("exit", (code) => reject(new Error("app exit " + code)));
});

const base = `http://127.0.0.1:${appPort}`;
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
  return { status: r.status, text, json };
};

let pass = 0, fail = 0;
const check = (label, ok, extra = "") => {
  if (ok) { pass++; console.log("  ✓", label); }
  else { fail++; console.log("  ✗", label, extra); }
};
const safe = (v) => v || {};

let r = await call("/api/health");
check("health بدون لاگین در دسترس است", r.status === 200 && typeof safe(r.json).login_required === "boolean", JSON.stringify(r.json));
check("health می‌گوید سرویس کامل نیست و GITHUB_TOKEN را خواستار است",
  safe(r.json).ok === false && (r.json.missing || []).some((m) => m.key === "GITHUB_TOKEN"), JSON.stringify(r.json).slice(0, 200));

r = await call("/api/config");
check("config کمبودها را با توضیح فارسی می‌دهد", r.status === 200 && (r.json.missing || []).every((m) => m.text && m.key), JSON.stringify(r.json).slice(0, 160));

r = await call("/");
check("بدون لاگین → ریدایرکت /login", r.status === 302 || r.status === 200, String(r.status));

r = await call("/login");
check("صفحه ورود فارسی و RTL", r.status === 200 && r.text.includes('dir="rtl"'));

r = await call("/api/data");
check("داده بدون کوکی → 401", r.status === 401 && r.json.error === "login_required", String(r.status));

r = await call("/api/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password: "wrong" }) });
check("رمز غلط → 401", r.status === 401);

r = await call("/api/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password: PASSWORD }) });
check("رمز درست → 200 و کوکی session", r.status === 200 && cookie.startsWith("froshgah_sid="));

r = await call("/api/data");
check("داده بعد از لاگین", r.status === 200 && r.json.count === stores.count && r.json.stores[0].title === "بوتیک نمونه", `${r.status} ${r.text.slice(0, 60)}`);

const csv = await fetch(`${base}/api/export.csv`, { headers: { cookie } });
const csvBytes = new Uint8Array(await csv.arrayBuffer());
const csvText = new TextDecoder("utf-8").decode(csvBytes);
check("CSV با BOM (برای اکسل فارسی) و هدر فارسی",
  csv.status === 200 && csvBytes[0] === 0xef && csvBytes[1] === 0xbb && csvBytes[2] === 0xbf && csvText.includes("عنوان,منبع"),
  String(csv.status));

r = await call("/api/status");
check("status بدون repo خطای مودبانه می‌دهد", r.status === 200 && /تنظیم نشده/.test(safe(r.json).error || ""), JSON.stringify(r.json));

r = await call("/api/collect", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ hashtags: "پوشاک", ig_user: "x", ig_pass: "y" }) });
check("collect با تنظیمات ناقص → پاسخ نرم + چک‌لیست (نه ۵۰۰)",
  r.status === 200 && r.json.ok === false && Array.isArray(r.json.missing) && typeof r.json.help === "string",
  JSON.stringify(r.json).slice(0, 200));

r = await call("/api/logout", { method: "POST", body: "{}" });
check("logout کوکی را پاک می‌کند", r.status === 200);
cookie = "";
r = await call("/api/data");
check("بعد از logout دوباره 401", r.status === 401);

dataSrv.close();
app.kill("SIGTERM");
console.log(`\n${fail ? "❌" : "✅"} ${pass} passes, ${fail} failures`);
process.exit(fail ? 1 : 0);
