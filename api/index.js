/* سرویس وب فروشگاه‌یاب روی Vercel — بدون هیچ وابستگی npm.
 *
 * کارها:
 *   /api/login      ورود با رمز سایت (SITE_PASSWORD) → کوکی امضاشده
 *   /api/data       فایل data/stores.json را از گیت‌هاب می‌خواند (فقط برای کاربر لاگین‌کرده)
 *   /api/status     آخرین کامیت داده + وضعیت آخرین اجرای workflow
 *   /api/collect    ارسال درخواست جمع‌آوری به GitHub Actions (رمزها فقط رمزنگاری‌شده و یک‌بارمصرف‌اند)
 *   /api/export.csv خروجی CSV برای اکسل
 *   /api/unlock     بازکردن قفل (همان لاگین، برای فراخوانی‌های JS)
 *
 * این برنامه هیچ‌چیز روی خودش ذخیره نمی‌کند: منبع حقیقت همان data/stores.json داخل مخزن است.
 */
"use strict";

const crypto = require("crypto");

/* نام مخزن و شاخه راز نیستند (روی گیت‌هاب عمومی دیده می‌شوند)، پس پیش‌فرضشان داخل کد است
 * تا لازم نباشد برای آن‌ها در Vercel متغیر بسازید. اگر متغیر را ست کنید (حتی با مقدار خالی)
 * همان پیش‌فرض را می‌پوشاند. بعد از ادغام روی main، مقدار GITHUB_REF=main را در Vercel بگذارید. */
const DEFAULTS = { repo: "aminchat/Froshgah", ref: "arena/e5aae2ae-froshgah" };
const envOr = (name, fallback) => (process.env[name] === undefined ? fallback : process.env[name]);

const CFG = {
  repo: envOr("GITHUB_REPO", DEFAULTS.repo),      // مثل: aminchat/Froshgah
  ref: envOr("GITHUB_REF", DEFAULTS.ref),
  token: process.env.GITHUB_TOKEN || "",          // fine-grained PAT (Contents: RW)
  workflow: process.env.WORKFLOW_FILE || "collect.yml",
  dataPath: process.env.DATA_PATH || "data/stores.json",
  password: process.env.SITE_PASSWORD || "",
  secret: process.env.APP_SECRET || process.env.SITE_PASSWORD || "froshgah-dev-secret",
  dataUrl: process.env.DATA_URL || "",
  allowPublic: process.env.ALLOW_PUBLIC_DATA === "1",
  apiBase: process.env.GITHUB_API || "https://api.github.com",
  sessionHours: Number(process.env.SESSION_HOURS || 12),
};

const KEY = crypto.createHash("sha256").update(String(CFG.secret)).digest();
const SESSION_TTL_MS = CFG.sessionHours * 3600 * 1000;
const cache = { data: null, at: 0, status: null, statusAt: 0 };
const rate = new Map();

const RAW_BASE = "https://raw.githubusercontent.com";

/* —————————— ابزارها —————————— */
const b64url = (buf) => Buffer.from(buf).toString("base64url");
const fromB64url = (s) => Buffer.from(s, "base64url");

function sign(parts) {
  return crypto.createHmac("sha256", KEY).update(parts).digest("base64url");
}

function makeSession() {
  const body = b64url(JSON.stringify({ exp: Date.now() + SESSION_TTL_MS }));
  return `${body}.${sign(body)}`;
}

function readSession(req) {
  const raw = req.headers.cookie || "";
  const m = /(?:^|;\s*)froshgah_sid=([^;]+)/.exec(raw);
  if (!m) return null;
  const [body, mac] = m[1].split(".");
  if (!body || !mac) return null;
  const expect = sign(body);
  if (mac.length !== expect.length || !crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(expect))) return null;
  try {
    const parsed = JSON.parse(fromB64url(body).toString("utf8"));
    return parsed.exp > Date.now() ? parsed : null;
  } catch {
    return null;
  }
}

function encryptPayload(obj) {
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv("aes-256-gcm", KEY, iv);
  const ct = Buffer.concat([c.update(JSON.stringify(obj), "utf8"), c.final()]);
  return Buffer.concat([iv, ct, c.getAuthTag()]).toString("base64");
}

function parseBody(req, limit = 64 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > limit) {
        reject(new Error("payload too large"));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      if (!text) return resolve({});
      try {
        resolve(JSON.parse(text));
      } catch {
        reject(new Error("bad json"));
      }
    });
    req.on("error", reject);
  });
}

function send(res, code, body, headers = {}) {
  const isObj = typeof body === "object" && body !== null && !Buffer.isBuffer(body);
  const data = isObj ? JSON.stringify(body) : body;
  res.writeHead(code, {
    "content-type": isObj ? "application/json; charset=utf-8" : "text/plain; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "content-length": Buffer.byteLength(data),
    ...headers,
  });
  res.end(data);
}

function tooFast(ip) {
  const now = Date.now();
  const hit = rate.get(ip) || { n: 0, at: now };
  if (now - hit.at > 60_000) Object.assign(hit, { n: 0, at: now });
  hit.n += 1;
  rate.set(ip, hit);
  return hit.n > 12;
}

function gh(path, opts = {}) {
  const headers = {
    "user-agent": "froshgah-web",
    accept: "application/vnd.github+json",
    "x-github-api-version": "2022-11-28",
    ...(opts.headers || {}),
  };
  if (CFG.token) headers.authorization = `Bearer ${CFG.token}`;
  return fetch(`${CFG.apiBase}${path}`, { ...opts, headers });
}

async function fetchText(url) {
  const r = await fetch(url, { headers: { "user-agent": "froshgah-web", accept: "application/json" } });
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.text();
}

function problems() {
  const list = [];
  if (!CFG.repo) {
    list.push({ key: "GITHUB_REPO", text: "نام مخزن را تنظیم کنید (مثلاً aminchat/Froshgah) تا داده از همان‌جا خوانده شود." });
  }
  if (!CFG.token) {
    list.push({
      key: "GITHUB_TOKEN",
      text: "برای دکمه «جمع‌آوری» یک Fine-grained PAT لازم است (Actions: write + Contents: read). اگر نمی‌خواهید، جمع‌آوری را با اسکریپت Codespaces انجام دهید؛ سایت باز هم نتایج را نشان می‌دهد.",
      blocks_collect: true,
    });
  }
  if (!CFG.password && !CFG.allowPublic) {
    list.push({ key: "SITE_PASSWORD", text: "رمز ورود سایت تنظیم نشده — تا ALLOW_PUBLIC_DATA=1 نگذارید، هیچ‌کس نمی‌تواند ببیند." });
  }
  if (CFG.secret === "froshgah-dev-secret") {
    list.push({ key: "APP_SECRET", text: "APP_SECRET هنوز مقدار پیش‌فرض است؛ یک عبارت تصادفی بگذارید و همان را در GitHub Actions Secret هم بگذارید." });
  }
  return list;
}

/* —————————— داده —————————— */
function dataUrl() {
  if (CFG.dataUrl) return CFG.dataUrl;
  if (!CFG.repo) return "";
  return `${RAW_BASE}/${CFG.repo}/${CFG.ref}/${CFG.dataPath}`;
}

async function getData(maxAgeMs = 60_000) {
  if (cache.data && Date.now() - cache.at < maxAgeMs) return cache.data;
  const url = dataUrl();
  if (!url) return { generated_at: "", count: 0, stores: [], error: "GITHUB_REPO تنظیم نشده" };
  const text = await fetchText(url);
  const parsed = JSON.parse(text);
  cache.data = parsed;
  cache.at = Date.now();
  return parsed;
}

async function getStatus() {
  if (cache.status && Date.now() - cache.statusAt < 20_000) return cache.status;
  const out = { repo: CFG.repo, ref: CFG.ref, data: null, run: null, error: "" };
  if (!CFG.repo) {
    out.error = "GITHUB_REPO تنظیم نشده است";
    return out;
  }
  try {
    const r = await gh(`/repos/${CFG.repo}/commits?path=${encodeURIComponent(CFG.dataPath)}&per_page=1`);
    if (r.ok) {
      const c = (await r.json())[0];
      if (c) out.data = { commit: c.sha.slice(0, 7), at: c.commit.author?.date || "", message: c.commit.message.split("\n")[0] };
    }
    if (CFG.workflow) {
      const w = await gh(`/repos/${CFG.repo}/actions/workflows/${encodeURIComponent(CFG.workflow)}/runs?per_page=1`);
      if (w.ok) {
        const run = (await w.json()).workflow_runs?.[0];
        if (run) {
          out.run = {
            status: run.status,
            conclusion: run.conclusion,
            at: run.created_at || "",
            url: run.html_url,
            branch: run.head_branch,
            event: run.event,
          };
        }
      }
    }
  } catch (e) {
    out.error = String(e.message || e);
  }
  cache.status = out;
  cache.statusAt = Date.now();
  return out;
}

function toCsv(stores) {
  const cols = ["title", "source", "city", "phones", "instagram", "telegram", "website", "categories", "url", "last_seen"];
  const esc = (v) => `"${String(Array.isArray(v) ? v.join(" | ") : v ?? "").replace(/"/g, '""')}"`;
  const rows = stores.map((d) => cols.map((c) => esc(d[c])).join(","));
  return "\uFEFF" + ["عنوان,منبع,شهر,تلفن,اینستاگرام,تلگرام,سایت,دسته‌ها,لینک,آخرین مشاهده", ...rows].join("\r\n");
}

/* —————————— مسیرها —————————— */
async function api(req, res, path) {
  const authed = Boolean(readSession(req)) || (!CFG.password && CFG.allowPublic);

  if (path === "/api/health" || path === "/api/config") {
    const list = problems();
    return send(res, 200, {
      ok: list.length === 0,
      login_required: Boolean(CFG.password),
      data_source: dataUrl() ? (CFG.dataUrl ? "custom" : "github") : "unset",
      can_dispatch: Boolean(CFG.repo && CFG.token),
      repo: CFG.repo,
      ref: CFG.ref,
      workflow: CFG.workflow,
      missing: list,
    });
  }

  if (path === "/api/login" && req.method === "POST") {
    const ip = req.headers["x-forwarded-for"] || "local";
    if (tooFast(ip)) return send(res, 429, { error: "چند بار پشت سر هم؛ یک دقیقه صبر کنید." });
    const body = await parseBody(req);
    const given = String(body.password || "");
    if (!CFG.password) return send(res, 200, { ok: true, note: "این نصب رمز عبور ندارد" });
    if (
      given.length !== CFG.password.length ||
      !crypto.timingSafeEqual(Buffer.from(given), Buffer.from(CFG.password))
    ) {
      return send(res, 401, { error: "رمز درست نیست." });
    }
    return send(res, 200, { ok: true }, {
      "set-cookie": `froshgah_sid=${makeSession()}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${CFG.sessionHours * 3600}${req.headers["x-forwarded-proto"] === "https" ? "; Secure" : ""}`,
    });
  }

  if (path === "/api/logout" && req.method === "POST") {
    return send(res, 200, { ok: true }, { "set-cookie": "froshgah_sid=; Path=/; HttpOnly; Max-Age=0" });
  }

  if (!authed) {
    const why = CFG.password ? { error: "login_required", login_url: "/login" }
      : { error: "not_configured", message: "رمز سایت را در Vercel (SITE_PASSWORD) تنظیم کنید یا ALLOW_PUBLIC_DATA=1 بگذارید." };
    return send(res, CFG.password ? 401 : 503, why);
  }

  if (path === "/api/session") return send(res, 200, { ok: true });

  if (path === "/api/data") {
    try {
      const data = await getData(Number(process.env.DATA_TTL_MS || 60_000));
      return send(res, 200, data, { "cache-control": "private, max-age=30" });
    } catch (e) {
      return send(res, 502, { error: String(e.message || e) });
    }
  }

  if (path === "/api/status") {
    return send(res, 200, await getStatus());
  }

  if (path === "/api/export.csv") {
    try {
      const data = await getData(0);
      return send(res, 200, toCsv(data.stores || []), {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": 'attachment; filename="froshgah.csv"',
      });
    } catch (e) {
      return send(res, 502, { error: String(e.message || e) });
    }
  }

  if (path === "/api/collect" && req.method === "POST") {
    const blocked = problems().filter((p) => p.blocks_collect || p.key === "GITHUB_REPO");
    if (blocked.length) {
      return send(res, 200, {
        ok: false,
        message: "سرویس هنوز به گیت‌هاب وصل نشده، برای همین هیچ جمعی انجام نمی‌شود.",
        missing: blocked,
        help: "دو راه: (۱) در Vercel متغیرهای GITHUB_REPO و GITHUB_TOKEN را پر کنید، (۲) یا جمع‌آوری را با ./scripts/collect-and-publish.sh در Codespaces اجرا کنید — سایت فقط نمایش می‌دهد.",
      });
    }
    const b = await parseBody(req);
    const clean = (v, n = 120) => String(v ?? "").trim().slice(0, n);
    const list = (v) => clean(v, 400).split(/[,\n]/).map((x) => x.trim().replace(/^#/, "")).filter(Boolean).slice(0, 12);
    const payload = {
      hashtags: list(b.hashtags),
      keywords: list(b.keywords),
      queries: list(b.queries),
      limit: Math.min(Math.max(Number(b.limit) || 25, 1), 100),
      bios: Boolean(b.bios),
      ig_user: clean(b.ig_user, 80),
      ig_pass: clean(b.ig_pass, 120),
      tg_api_id: clean(b.tg_api_id, 40),
      tg_api_hash: clean(b.tg_api_hash, 80),
      requested_by: "web",
      requested_at: new Date().toISOString(),
    };
    if (!payload.hashtags.length && !payload.keywords.length && !payload.queries.length) {
      return send(res, 422, { error: "حداقل یک هشتگ یا عبارت بنویسید." });
    }
    const encrypted = encryptPayload(payload);
    const r = await gh(`/repos/${CFG.repo}/actions/workflows/${encodeURIComponent(CFG.workflow)}/dispatches`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ref: CFG.ref,
        inputs: { payload: encrypted, source: "web" },
      }),
    });
    if (r.status !== 204 && r.status !== 200) {
      const text = (await r.text()).slice(0, 400);
      return send(res, 502, {
        error: `گیت‌هاب پاسخ نداد (${r.status})`,
        detail: text,
        hint: r.status === 404
          ? "فایل workflow باید روی شاخه پیش‌فرض مخزن باشد تا بشود آن را از بیرون اجرا کرد."
          : "احتمال PAT منقضی شده یا اجازه actions:write ندارد.",
      });
    }
    cache.statusAt = 0;
    return send(res, 200, {
      ok: true,
      message: "جمع‌آوری آغاز شد؛ نتیجه چند دقیقه دیگر در سایت ظاهر می‌شود.",
      counts: { hashtags: payload.hashtags.length, keywords: payload.keywords.length, queries: payload.queries.length },
    });
  }

  return send(res, 404, { error: "not_found", path });
}

const LOGIN_HTML = `<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ورود · فروشگاه‌یاب</title>
<link rel="stylesheet" href="/style.css"></head><body class="auth">
<main class="authbox"><h1>🏪 فروشگاه‌یاب پوشاک</h1><p>این صفحه خصوصی است. رمز سایت را وارد کنید.</p>
<form id="f"><input id="p" type="password" placeholder="رمز" autocomplete="current-password" autofocus>
<button type="submit">ورود</button></form><p id="m" class="err"></p>
<small>رمز را فراموش کردید؟ در Vercel متغیر SITE_PASSWORD را ببینید یا عوض کنید.</small></main>
<script>
const f=document.getElementById('f'),m=document.getElementById('m');
f.addEventListener('submit',async(e)=>{e.preventDefault();m.textContent='';
 const r=await fetch('/api/login',{method:'POST',headers:{'content-type':'application/json'},
 body:JSON.stringify({password:document.getElementById('p').value})});
 if(r.ok)location.href='/?'+Date.now(); else m.textContent=(await r.json()).error||'خطا';});
</script></body></html>`;

module.exports = async function handler(req, res) {
  const url = new URL(req.url, "http://x");
  const path = url.pathname.replace(/\/+$/, "") || "/";
  try {
    if (path.startsWith("/api/")) return await api(req, res, path);
    if (path === "/login") {
      const html = CFG.password
        ? LOGIN_HTML
        : LOGIN_HTML.replace("رمز سایت را وارد کنید.", "<b>SITE_PASSWORD</b> هنوز در Vercel تنظیم نشده است — بعد از تنظیم، همین‌جا وارد شوید.");
      res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" });
      return res.end(html);
    }
    if (path === "/" || path === "/index.html") {
      if (!CFG.allowPublic && !readSession(req)) {
        res.writeHead(302, { location: "/login" });
        return res.end();
      }
    }
    return send(res, 404, { error: "این مسیر را سرویس وب ندارد؛ فایل‌های سایت توسط خود Vercel سرو می‌شوند." });
  } catch (e) {
    return send(res, 500, { error: String(e && e.message ? e.message : e) });
  }
};

module.exports.config = { maxDuration: 30 };
