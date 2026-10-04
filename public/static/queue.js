/* Sugar's queue: PIN gate + live order cards with FLIP reordering. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const naira = (n) => "₦" + Number(n || 0).toLocaleString("en-NG");
  const SHADES = { "Nude": "#e6b8a2", "Milky white": "#f7f1ec", "Baby pink": "#f6c3cd", "Hot pink": "#ec4f8c", "Red": "#c8102e",
    "Wine": "#6b1a2b", "Black": "#1f1a1c", "Chocolate brown": "#5a3326", "Gold": "#d4a646", "Silver": "#c9c9d1",
    "Emerald green": "#1f7a5a", "Sky blue": "#8cc4e8", "Lilac": "#c9b3dd", "Coral": "#f27e6b" };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let pin = sessionStorage.getItem("sugar-pin") || "";
  let menu = { services: {}, styles: {}, lengths: {} };
  let known = new Set(), first = true, chime = true, timer = null;

  fetch("/api/menu").then((r) => r.json()).then((m) => {
    m.services.forEach((s) => (menu.services[s.id] = s.label));
    m.styles.forEach((s) => (menu.styles[s.id] = s.label));
    m.lengths.forEach((s) => (menu.lengths[s.id] = s.label));
  });

  /* ---------- PIN gate ---------- */
  let entry = "";
  const dots = [...document.querySelectorAll("#dots i")];
  const paint = () => dots.forEach((d, i) => d.classList.toggle("on", i < entry.length));
  $("#pad").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.k === "del") entry = entry.slice(0, -1); else if (entry.length < 4) entry += b.textContent;
    paint();
    if (entry.length === 4) tryPin(entry);
  });
  addEventListener("keydown", (e) => {
    if (!$("#gate").hidden) {
      if (/^\d$/.test(e.key) && entry.length < 4) { entry += e.key; paint(); if (entry.length === 4) tryPin(entry); }
      if (e.key === "Backspace") { entry = entry.slice(0, -1); paint(); }
    }
  });
  async function tryPin(p) {
    const r = await fetch("/api/queue/login", { method: "POST", headers: { "X-Pin": p } });
    if (r.ok) { pin = p; sessionStorage.setItem("sugar-pin", p); open(); }
    else { $("#dots").classList.add("shake"); setTimeout(() => { $("#dots").classList.remove("shake"); entry = ""; paint(); }, 450); }
  }
  function open() { $("#gate").hidden = true; $("#dash").hidden = false; refresh(); timer = setInterval(refresh, 3000); }
  $("#lock").addEventListener("click", () => { sessionStorage.removeItem("sugar-pin"); location.reload(); });
  $("#sound").addEventListener("click", (e) => { chime = !chime; e.target.textContent = chime ? "🔔 Chime on" : "🔕 Chime off"; e.target.setAttribute("aria-pressed", chime); });

  function ding() {
    if (!chime) return;
    try {
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      [880, 1320].forEach((f, i) => { const o = ac.createOscillator(), g = ac.createGain(); o.frequency.value = f; o.type = "sine";
        g.gain.setValueAtTime(0.0001, ac.currentTime + i * 0.12); g.gain.exponentialRampToValueAtTime(0.15, ac.currentTime + i * 0.12 + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + i * 0.12 + 0.5); o.connect(g).connect(ac.destination); o.start(ac.currentTime + i * 0.12); o.stop(ac.currentTime + i * 0.12 + 0.6); });
    } catch {}
  }
  function toast(t) { const el = $("#toast"); el.textContent = t; el.classList.add("show"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), 3200); }

  /* ---------- render ---------- */
  function card(b) {
    const o = b.order, st = b.status;
    const sw = (o.colours || []).filter((c) => c !== "None").map((c) => `<i style="background:${SHADES[c] || "#ddd"}"></i>`).join("");
    const notes = o.notes && o.notes !== "None";
    const label = st === "in_chair" ? "✦" : st === "done" ? "✓" : b.position;
    const mins = Math.max(0, Math.round((Date.now() / 1000 - b.queued_at) / 60));
    return `<article class="qcard ${st === "in_chair" ? "chair" : ""}" data-id="${b.id}">
      <div class="qtop"><div class="qnum">${label}</div>
        <div><div class="qname">${esc(o.name)}</div><div class="qmeta">${esc(o.phone)} · ${esc(o.time)} · booked ${mins}m ago</div></div>
        <span class="paid ${b.pay_mode === "mock" ? "test" : ""}">${b.pay_mode === "mock" ? "Paid · test" : "Paid"}</span></div>
      <div class="qsvc">${o.services.map((s) => `<span>${esc(menu.services[s] || s)}</span>`).join("")}</div>
      <dl class="qgrid">
        <dt>Style</dt><dd>${esc(menu.styles[o.style] || o.style)}</dd>
        <dt>Colours</dt><dd><span class="swatches">${sw}</span>${esc((o.colours || []).join(", "))}</dd>
        ${o.length !== "natural" ? `<dt>Length</dt><dd>${esc(menu.lengths[o.length] || o.length)}</dd>` : ""}
        ${o.shape !== "n/a" ? `<dt>Shape</dt><dd>${esc(o.shape)}</dd>` : ""}
        <dt>Notes</dt><dd>${notes ? `<span class="note-hot">⚠ ${esc(o.notes)}</span>` : "None"}</dd>
      </dl>
      <div class="qfoot"><b>${naira(b.total)}</b>
        ${st === "paid" ? `<button class="pill small plum" data-act="start">Start</button>` : st === "in_chair" ? `<button class="pill small" data-act="done">Done ✓</button>` : ""}
      </div></article>`;
  }

  // FLIP: remember positions, re-render, animate from old to new spot
  function renderAll(list) {
    const rects = new Map();
    document.querySelectorAll(".qcard").forEach((el) => rects.set(el.dataset.id, el.getBoundingClientRect()));
    const groups = { chair: list.filter((b) => b.status === "in_chair"), next: list.filter((b) => b.status === "paid"), done: list.filter((b) => b.status === "done").slice(0, 12) };
    const empty = { chair: "Nobody in the chair. Tap <b>Start</b> on the next client.", next: "No one waiting yet. New bookings pop up here by themselves.", done: "" };
    for (const [k, items] of Object.entries(groups)) {
      $("#" + k).innerHTML = items.length ? items.map(card).join("") : empty[k] ? `<p class="empty">${empty[k]}</p>` : "";
    }
    document.querySelectorAll(".qcard").forEach((el) => {
      const old = rects.get(el.dataset.id);
      if (!old) { if (!first && !reduce) el.classList.add("enter"); return; }
      if (reduce) return;
      const now = el.getBoundingClientRect(), dx = old.left - now.left, dy = old.top - now.top;
      if (dx || dy) el.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: "none" }], { duration: 650, easing: "cubic-bezier(.2,.8,.2,1)" });
    });
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const todays = list.filter((b) => b.queued_at * 1000 >= today.getTime());
    bump("#sWait", groups.next.length); bump("#sChair", groups.chair.length);
    bump("#sDone", list.filter((b) => b.status === "done").length);
    bump("#sMoney", naira(todays.reduce((a, b) => a + b.total, 0)));
  }
  function bump(sel, v) { const el = $(sel); if (el.textContent != v) { el.textContent = v; if (!reduce) el.animate([{ transform: "scale(1.3)" }, { transform: "none" }], { duration: 400, easing: "cubic-bezier(.34,1.56,.64,1)" }); } }

  async function refresh() {
    const r = await fetch("/api/queue", { headers: { "X-Pin": pin } }).catch(() => null);
    if (!r) return;
    if (r.status === 401) { sessionStorage.removeItem("sugar-pin"); location.reload(); return; }
    const { queue } = await r.json();
    const fresh = queue.filter((b) => !known.has(b.id));
    if (!first && fresh.length) { ding(); toast(`New booking: ${fresh[0].order.name} · ${naira(fresh[0].total)}`); }
    queue.forEach((b) => known.add(b.id));
    renderAll(queue); first = false;
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]"); if (!btn) return;
    const el = btn.closest(".qcard"); btn.disabled = true;
    const r = await fetch(`/api/queue/${el.dataset.id}/${btn.dataset.act}`, { method: "POST", headers: { "X-Pin": pin } });
    if (r.ok) { if (btn.dataset.act === "done") toast("Lovely work! ✨"); await refresh(); } else btn.disabled = false;
  });

  if (pin) fetch("/api/queue/login", { method: "POST", headers: { "X-Pin": pin } }).then((r) => r.ok ? open() : sessionStorage.removeItem("sugar-pin"));
})();
