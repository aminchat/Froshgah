/* پنل جمع‌آوری — فقط وقتی فعال است که سرویس وب (Vercel) کنار سایت باشد.
 * برای نسخه GitHub Pages (فایل ایستا) این اسکریپت هیچ کاری نمی‌کند.
 */
(() => {
  "use strict";
  const CFG = window.FROSHGAH || {};
  if (!CFG.api) return;

  const $ = (id) => document.getElementById(id);
  const bar = $("collectbar");
  const dlg = $("dlg");
  const msg = $("dlgmsg");
  const state = $("runstate");
  if (!bar || !dlg) return;
  bar.hidden = false;

  const FIELDS = ["hashtags", "queries", "ig_user", "ig_pass", "tg_api_id", "tg_api_hash", "limit", "bios", "remember"];
  const KEY = "froshgah.vault";
  let loading = false;

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
      for (const k of FIELDS) {
        if (saved[k] === undefined) continue;
        const el = $(k);
        if (!el) continue;
        if (el.type === "checkbox") el.checked = Boolean(saved[k]);
        else el.value = saved[k];
      }
    } catch { /* ignore */ }
  }
  function save() {
    const data = {};
    for (const k of FIELDS) {
      const el = $(k);
      if (!el) continue;
      data[k] = el.type === "checkbox" ? el.checked : el.value;
    }
    if (data.remember) localStorage.setItem(KEY, JSON.stringify(data));
    else localStorage.removeItem(KEY);
  }

  function renderMissing(list, prefix = "") {
    const box = $("cfglist");
    if (!box) return;
    if (!list || !list.length) {
      box.hidden = true;
      box.textContent = "";
      return;
    }
    box.hidden = false;
    box.innerHTML = `<b>${prefix || "تنظیمات لازم:"}</b><ul>` +
      list.map((p) => `<li><code>${p.key}</code> — ${p.text}</li>`).join("") + `</ul>`;
  }

  $("openCollect").addEventListener("click", () => {
    load();
    msg.textContent = "";
    dlg.showModal();
    checkConfig();
  });

  async function checkConfig() {
    try {
      const r = await fetch("/api/config", { cache: "no-store", credentials: "same-origin" });
      if (!r.ok) return;
      const cfg = await r.json();
      cfgRef = cfg;
      renderMissing(cfg.ok ? [] : cfg.missing, cfg.ok ? "" : "قبل از کلیک، این‌ها را کامل کنید:");
      state.textContent = cfg.ok
        ? `✓ سرویس آماده است · مخزن ${cfg.repo}@${cfg.ref}`
        : `⚠️ سرویس آماده نیست: ${cfg.missing.map((m) => m.key).join("، ")}`;
    } catch { /* سرویس در دسترس نیست */ }
  }

  async function post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await r.json(); } catch { /* empty body */ }
    if (!r.ok) {
      if (r.status === 401) { location.href = "/login"; throw new Error("login required"); }
      throw new Error(data.error || `HTTP ${r.status}`);
    }
    return data;
  }

  $("go").addEventListener("click", async () => {
    if (loading) return;
    loading = true;
    const btn = $("go");
    const old = btn.textContent;
    btn.textContent = "در حال ارسال…";
    msg.className = "err";
    msg.textContent = "";
    const body = {
      hashtags: $("hashtags").value,
      keywords: "",
      queries: $("queries").value,
      limit: Number($("limit").value || 25),
      bios: $("bios").checked,
      ig_user: $("ig_user").value.trim(),
      ig_pass: $("ig_pass").value,
      tg_api_id: $("tg_api_id").value.trim(),
      tg_api_hash: $("tg_api_hash").value.trim(),
    };
    try {
      const out = await post("/api/collect", body);
      if (out.ok === false) {
        msg.className = "err";
        msg.textContent = `⚠️ ${out.message}`;
        renderMissing(out.missing, "برای فعال‌شدن این دکمه:");
        if (out.help) {
          const box = $("cfghelp");
          if (box) { box.hidden = false; box.textContent = out.help; }
        }
        return;
      }
      save();
      msg.className = "ok";
      msg.textContent = `✅ ${out.message} (${out.counts.hashtags} هشتگ، ${out.counts.queries} عبارت تلگرام)`;
      refreshStatus(true);
    } catch (e) {
      const hint = e.message && e.message.includes("401") ? "" : "";
      msg.textContent = `⚠️ ${e.message}${hint}`;
    } finally {
      btn.textContent = old;
      loading = false;
    }
  });

  let timer = null;
  let cfgRef = null;
  async function refreshStatus(force) {
    try {
      const r = await fetch("/api/status", { cache: "no-store" });
      if (!r.ok) return;
      const s = await r.json();
      const bits = [];
      if (s.data) bits.push(`آخرین داده: ${String(s.data.at || "").slice(0, 16).replace("T", " ")}`);
      if (s.run) {
        const running = s.run.status === "in_progress" || s.run.status === "queued";
        const done = s.run.conclusion === "success";
        bits.push(running ? "⏳ جمع‌آوری در حال اجرا…" : done ? "✓ آخرین اجرا موفق" : `⚠ آخرین اجرا: ${s.run.conclusion || s.run.status}`);
        if (running) {
          if (!timer) timer = setInterval(() => refreshStatus(true), 20000);
        } else if (timer) {
          clearInterval(timer);
          timer = null;
        }
      }
      if (s.error) bits.push(`(خطای وضعیت: ${s.error})`);
      state.textContent = bits.join(" · ");
      if (force) setTimeout(() => location.reload(), 2500);
    } catch { /* سرویس در دسترس نیست */ }
  }
  checkConfig();
  refreshStatus(false);
})();
