/* فروشگاه‌یاب — جستجوی سمت کلاینت روی فایل داده‌های JSON */
(() => {
  "use strict";

  const PAGE = 30;
  const APPCFG = window.FROSHGAH || {};
  const DATA_SRC = APPCFG.data || "data/stores.json";
  const state = { all: [], view: [], tokens: [], limit: PAGE, generated: "" };
  const $ = (id) => document.getElementById(id);
  const els = {
    q: $("q"), clear: $("clear"), source: $("source"), city: $("city"), cat: $("cat"),
    onlyphone: $("onlyphone"), sort: $("sort"), results: $("results"), meta: $("meta"),
    summary: $("summary"), more: $("more"), moreBtn: $("moreBtn"),
  };

  /* —— نرمال‌سازی فارسی (همان منطق normalize.py) —— */
  const AR_DIGITS = /[۰-۹٠-٩]/g;
  const DIACRITICS = /[ً-ْٰـ]/g;
  function norm(s) {
    return String(s == null ? "" : s)
      .replace(AR_DIGITS, (d) => {
        const c = d.charCodeAt(0);
        return String(c >= 0x06f0 ? c - 0x06f0 : c - 0x0660);
      })
      .replace(/[يى]/g, "ی").replace(/ك/g, "ک").replace(/ة/g, "ه")
      .replace(DIACRITICS, "").replace(/‌/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fa = (n) => Number(n).toLocaleString("fa-IR");
  const uniq = (a) => [...new Set(a.filter(Boolean))];

  function hay(d) {
    return norm([d.title, d.username, d.city, d.url, d.instagram, d.telegram, d.website,
      (d.categories || []).join(" "), (d.phones || []).join(" "), d.text, d.source_key].join(" "));
  }

  function highlight(text, tokens) {
    let out = esc(text);
    for (const t of tokens) {
      if (!t) continue;
      const rx = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      out = out.replace(rx, (m) => `<mark>${m}</mark>`);
    }
    return out;
  }

  function score(d, tokens) {
    let hits = 0;
    for (const t of tokens) if (d._hay.includes(t)) hits++;
    if (!hits) return 0;
    const full = hits === tokens.length ? 1000 : 0;
    const name = tokens.some((t) => d._name.includes(t)) ? 120 : 0;
    const user = tokens.some((t) => d._user.includes(t)) ? 80 : 0;
    const phone = (d.phones || []).length ? 25 : 0;
    const cat = tokens.some((t) => d._cats.includes(t)) ? 40 : 0;
    return full + name + user + cat + hits * 10 + phone;
  }

  function apply() {
    const tokens = norm(els.q.value).split(" ").filter(Boolean);
    const src = els.source.value, city = els.city.value, cat = els.cat.value;
    const onlyPhone = els.onlyphone.checked, sortByNew = els.sort.value === "new";

    let list = state.all.filter((d) => {
      if (src && d.source !== src) return false;
      if (city && d.city !== city) return false;
      if (cat && !(d.categories || []).includes(cat)) return false;
      if (onlyPhone && !(d.phones || []).length) return false;
      return true;
    });
    if (tokens.length) {
      list = list.map((d) => ({ d, s: score(d, tokens) })).filter((x) => x.s > 0);
      if (!sortByNew) {
        list.sort((a, b) => b.s - a.s || (a.d.last_seen < b.d.last_seen ? 1 : -1));
      } else {
        list.sort((a, b) => (a.d.last_seen > b.d.last_seen ? -1 : 1));
      }
      list = list.map((x) => x.d);
    } else {
      list.sort((a, b) => (a.last_seen > b.last_seen ? -1 : a.last_seen < b.last_seen ? 1 : 0));
    }
    state.view = list;
    state.tokens = tokens;
    state.limit = PAGE;
    render();
    updateUrl();
  }

  function render() {
    const list = state.view.slice(0, state.limit);
    els.results.innerHTML = "";
    if (!list.length) {
      els.results.innerHTML = `<div class="empty" style="grid-column:1/-1">
        <b>چیزی پیدا نشد</b>
        ${state.all.length ? "عبارت دیگری را امتحان کنید یا فیلترها را بردارید."
        : "دیتابیس خالی است — workflow «collect» را از تب Actions اجرا کنید."}</div>`;
    } else {
      for (const d of list) els.results.appendChild(card(d));
    }
    els.more.hidden = state.view.length <= list.length;
    const withPhone = state.view.filter((d) => (d.phones || []).length).length;
    els.summary.innerHTML =
      `<span>نمایش <b>${fa(list.length)}</b> از <b>${fa(state.view.length)}</b> نتیجه</span>` +
      (state.all.length ? `<span>کل رکوردها: <b>${fa(state.all.length)}</b></span>
        <span>دارای شماره: <b>${fa(withPhone)}</b></span>` : "");
  }

  function card(d) {
    const el = document.createElement("article");
    el.className = "card";
    const t = state.tokens || [];
    const title = d.title || d.username || "بدون نام";
    const parts = [];
    parts.push(`<div class="name"><h3>${highlight(title, t)}</h3>
      <span class="badge ${esc(d.source)}">${d.source === "instagram" ? "📸 اینستا" : "✈️ تلگرام"}</span></div>`);
    if (d.city) parts.push(`<div class="row">📍 <b>${esc(d.city)}</b></div>`);
    if ((d.phones || []).length) {
      parts.push(`<div class="row"><span class="k">📱</span>` +
        d.phones.map((p) => `<button class="phone" data-copy="${esc(p)}" title="کپی شماره">${esc(p)}</button>`).join("") +
        `</div>`);
    }
    const links = [];
    if (d.instagram) links.push(`<a href="https://www.instagram.com/${esc(d.instagram)}/" target="_blank" rel="noopener">📸 @${esc(d.instagram)}</a>`);
    if (d.telegram) links.push(`<a href="https://t.me/${esc(d.telegram)}" target="_blank" rel="noopener">✈️ @${esc(d.telegram)}</a>`);
    if (d.website) links.push(`<a href="${esc(/^(https?:)?\/\//.test(d.website) ? d.website : "https://" + d.website)}" target="_blank" rel="noopener">🌐 سایت</a>`);
    if (links.length) parts.push(`<div class="row">${links.join(" · ")}</div>`);
    if ((d.categories || []).length) {
      parts.push(`<div class="tags">` + d.categories.slice(0, 8).map((c) => `<span class="tag">${esc(c)}</span>`).join("") + `</div>`);
    }
    if (d.text) parts.push(`<div class="snippet">${esc(d.text).slice(0, 220)}</div>`);
    if (d.url) parts.push(`<div class="row"><a href="${esc(d.url)}" target="_blank" rel="noopener">🔗 منبع</a>
      <span class="seen">· آخرین مشاهده ${esc((d.last_seen || "").slice(0, 10))}</span></div>`);
    el.innerHTML = parts.join("");
    return el;
  }

  function fill(id, values) {
    const sel = $(id);
    const cur = sel.value;
    sel.length = 1;
    for (const v of values) sel.add(new Option(v, v));
    sel.value = values.includes(cur) ? cur : "";
  }

  function toast(msg) {
    const el = document.createElement("div");
    el.className = "toast on";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1600);
  }

  function updateUrl() {
    const u = new URL(location.href);
    state.tokens && state.tokens.length ? u.searchParams.set("q", state.tokens.join(" ")) : u.searchParams.delete("q");
    els.source.value ? u.searchParams.set("src", els.source.value) : u.searchParams.delete("src");
    history.replaceState(null, "", u);
  }

  async function boot() {
    els.results.innerHTML = ['','', ''].map(() => '<div class="skel"></div>').join("");
    let data;
    try {
      data = await fetch(new URL(DATA_SRC, document.baseURI), { cache: "no-store", credentials: "same-origin" })
        .then(async (r) => {
          if (r.status === 401 && APPCFG.login) { location.href = APPCFG.login; throw new Error("نیاز به ورود"); }
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        });
    } catch (e) {
      els.meta.textContent = "فایل داده پیدا نشد — اول workflow جمع‌آوری را اجرا کنید.";
      els.results.innerHTML = `<div class="empty" style="grid-column:1/-1"><b>داده‌ای وجود ندارد</b>${esc(String(e))}</div>`;
      return;
    }
    state.all = (data.stores || []).map((d) => ({
      ...d,
      _hay: hay(d),
      _name: norm(d.title),
      _user: norm(d.username + " " + (d.source_key || "")),
      _cats: norm((d.categories || []).join(" ")),
    }));
    state.generated = data.generated_at || "";
    els.meta.innerHTML = `<b>${fa(state.all.length)}</b> فروشگاه` +
      (state.generated ? ` · آخرین بروزرسانی ${esc(state.generated)}` : "");
    const cities = uniq(state.all.map((d) => d.city).sort((a, b) => a.localeCompare(b, "fa")));
    const cats = uniq(state.all.flatMap((d) => d.categories || [])).sort((a, b) => a.localeCompare(b, "fa"));
    fill("city", cities);
    fill("cat", cats);
    const params = new URLSearchParams(location.search);
    if (params.get("q")) els.q.value = params.get("q");
    if (params.get("src")) els.source.value = params.get("src");
    apply();
  }

  let timer = null;
  els.q.addEventListener("input", () => {
    els.clear.hidden = !els.q.value;
    clearTimeout(timer);
    timer = setTimeout(apply, 110);
  });
  els.clear.addEventListener("click", () => { els.q.value = ""; els.clear.hidden = true; apply(); els.q.focus(); });
  for (const k of ["source", "city", "cat", "sort"]) els[k].addEventListener("change", apply);
  els.onlyphone.addEventListener("change", apply);
  els.moreBtn.addEventListener("click", () => { state.limit += PAGE; render(); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]");
    if (!b) return;
    navigator.clipboard?.writeText(b.dataset.copy).then(() => toast("شماره کپی شد ✓"), () => {});
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== els.q) { e.preventDefault(); els.q.focus(); }
    if (e.key === "Escape" && document.activeElement === els.q) els.q.blur();
  });
  boot();
})();
