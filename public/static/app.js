/* Sugar Nails — customer site. Vanilla JS, no build step. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const naira = (n) => "₦" + Number(n || 0).toLocaleString("en-NG");
  const SHADES = { "Nude": "#e6b8a2", "Milky white": "#f7f1ec", "Baby pink": "#f6c3cd", "Hot pink": "#ec4f8c", "Red": "#c8102e",
    "Wine": "#6b1a2b", "Black": "#1f1a1c", "Chocolate brown": "#5a3326", "Gold": "#d4a646", "Silver": "#c9c9d1",
    "Emerald green": "#1f7a5a", "Sky blue": "#8cc4e8", "Lilac": "#c9b3dd", "Coral": "#f27e6b" };
  const STYLE_LOOK = {
    plain: () => "linear-gradient(160deg,#f6a5b5,#e47e93)",
    french: () => "linear-gradient(180deg,#fff 0 28%,#f3d3cf 30%)",
    ombre: () => "linear-gradient(180deg,#fff 0%,#f6c3cd 70%)",
    chrome: () => "linear-gradient(115deg,#f3e9ee,#c9b7c0 30%,#fff 45%,#bfa9b4 60%,#efe4e9)",
    cat_eye: () => "radial-gradient(ellipse 30% 60% at 60% 50%,#f7d27a 0%,#7d2a3a 60%,#3b0f19 100%)",
    marble: () => "linear-gradient(130deg,transparent 40%,#cfa7b0 42%,transparent 46%),linear-gradient(60deg,transparent 55%,#d9b5bd 57%,transparent 60%),#fbf3f4",
    nail_art: () => "radial-gradient(circle at 50% 35%,#c8566c 0 3px,transparent 4px),radial-gradient(circle at 40% 60%,#fff 0 2px,transparent 3px),linear-gradient(#f6c3cd,#f6c3cd)",
    stones: () => "radial-gradient(circle at 50% 25%,#fff 0 3px,#d5d8e6 4px,transparent 5px),radial-gradient(circle at 50% 45%,#fff 0 2px,transparent 3px),linear-gradient(#e6b8a2,#e6b8a2)",
    flowers_3d: () => "radial-gradient(circle at 50% 40%,#f7d27a 0 3px,#fff 4px 8px,transparent 9px),linear-gradient(#f6c3cd,#f6c3cd)",
  };
  const ICONS = {
    hand: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6e1f2e" stroke-width="1.8" stroke-linecap="round"><path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11m0-6.5a1.5 1.5 0 0 1 3 0V11m0-4.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-.5A6.5 6.5 0 0 1 4 15.5L3.5 14a1.5 1.5 0 0 1 2.6-1.4L8 15"/></svg>',
    gem: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6e1f2e" stroke-width="1.8" stroke-linejoin="round"><path d="M6 3h12l3 6-9 12L3 9z"/><path d="M3 9h18M9 3l3 18 3-18"/></svg>',
    foot: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6e1f2e" stroke-width="1.8" stroke-linecap="round"><path d="M7 21c-2 0-3-2-3-5 0-4 2-7 5-7s4 3 4 6-2 6-6 6z"/><circle cx="15" cy="5" r="1.5"/><circle cx="18.5" cy="7.5" r="1.2"/><circle cx="19.5" cy="11" r="1"/></svg>',
    bottle: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6e1f2e" stroke-width="1.8" stroke-linejoin="round"><rect x="9" y="2" width="6" height="7" rx="1.5"/><path d="M6 13a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3z"/></svg>',
  };
  const SVC_META = {
    gel_hands: ["bottle", "Glossy, chip-resistant colour that lasts 2–3 weeks.", "Popular"],
    gel_toes: ["foot", "Long-lasting gel shine for your toes."],
    acrylic_full: ["gem", "Strong, sculpted full set, any length and shape.", "Bestseller"],
    gelx: ["gem", "Lightweight soft-gel tips, natural feel, zero damage."],
    biab: ["hand", "Builder gel on your natural nails for strength and growth."],
    press_on: ["gem", "Custom-sized reusable set made just for you."],
    refill: ["hand", "Fill in the regrowth on your acrylics (2–3 weeks)."],
    manicure: ["hand", "Shape, cuticle care, buff and a little hand massage."],
    pedicure: ["foot", "Warm soak, scrub, callus care, mask and massage.", "Relaxing"],
    removal: ["bottle", "Gentle soak-off of old gel or acrylic."],
  };

  /* ---------- ambient motion ---------- */
  if (!reduce) {
    const b = $("#bubbles");
    for (let i = 0; i < 16; i++) {
      const s = document.createElement("span"), size = 8 + Math.random() * 26;
      Object.assign(s.style, { left: Math.random() * 100 + "%", width: size + "px", height: size + "px",
        animationDuration: 14 + Math.random() * 18 + "s", animationDelay: -Math.random() * 30 + "s" });
      s.style.setProperty("--dx", (Math.random() * 80 - 40) + "px");
      b.appendChild(s);
    }
  }
  document.querySelectorAll("[data-split]").forEach((w, wi) => {
    const t = w.textContent; w.textContent = "";
    [...t].forEach((ch, i) => { const c = document.createElement("span"); c.className = "char"; c.textContent = ch;
      c.style.animationDelay = (0.25 + wi * 0.3 + i * 0.06) + "s"; w.appendChild(c); });
  });
  const header = $(".site-header");
  addEventListener("scroll", () => header.classList.toggle("scrolled", scrollY > 10), { passive: true });
  const nav = $("#nav"), mb = $("#menuBtn");
  mb.addEventListener("click", () => { const o = nav.classList.toggle("open"); mb.setAttribute("aria-expanded", o); });
  nav.addEventListener("click", (e) => { if (e.target.closest("a")) nav.classList.remove("open"); });
  $("#yr").textContent = new Date().getFullYear();
  const hr = new Date().getHours();
  $("#openLine").textContent = hr >= 9 && hr < 20 ? "Open now · 9am – 8pm" : "Closed now · book for tomorrow";

  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 });
  const observe = (root = document) => root.querySelectorAll(".reveal:not(.in)").forEach((el) => io.observe(el));

  /* ---------- swatch wheel ---------- */
  const wheel = $("#wheel"), shades = Object.values(SHADES);
  shades.forEach((c, i) => {
    const a = (360 / shades.length) * i;
    wheel.insertAdjacentHTML("beforeend",
      `<g transform="rotate(${a} 200 200)"><path d="M200 18c-15 0-24 18-24 42v56c0 9 7 15 15 15h18c8 0 15-6 15-15V60c0-24-9-42-24-42z" fill="${c}" stroke="rgba(110,31,46,.12)"/>
       <path d="M188 40c-2 8-3 18-3 30" stroke="url(#shine)" stroke-width="6" stroke-linecap="round" fill="none"/></g>`);
  });

  /* ---------- menu from API ---------- */
  fetch("/api/menu").then((r) => r.json()).then((m) => {
    const grid = $("#menuGrid");
    m.services.forEach((s, i) => {
      const meta = SVC_META[s.id] || ["bottle", ""];
      grid.insertAdjacentHTML("beforeend", `<article class="svc reveal" style="--d:${(i % 4) * 0.07}s">
        ${meta[2] ? `<span class="tag">${meta[2]}</span>` : ""}<div class="icon">${ICONS[meta[0]]}</div>
        <h3>${s.label}</h3><p>${meta[1]}</p><div class="price">${naira(s.price)}</div></article>`);
    });
    const sg = $("#stylesGrid");
    m.styles.forEach((s, i) => {
      const bg = STYLE_LOOK[s.id] ? STYLE_LOOK[s.id]() : "#f6c3cd";
      sg.insertAdjacentHTML("beforeend", `<div class="style-card reveal" style="--d:${(i % 5) * 0.06}s"><div class="nails">
        ${[0, 1, 2].map((k) => `<span class="nail" style="--i:${k + i};background:${bg}"></span>`).join("")}</div>
        <b>${s.label}</b><span>${s.price ? "+" + naira(s.price) : "Included"}</span></div>`);
    });
    const pal = $("#palette");
    m.colours.forEach((c, i) => pal.insertAdjacentHTML("beforeend",
      `<div class="drop-wrap reveal" style="--d:${i * 0.04}s"><span class="drop" style="background:${SHADES[c] || "#f6c3cd"}"></span>${c}</div>`));
    observe();
  });
  observe();

  /* ---------- live queue count ---------- */
  let shown = 0;
  const countTo = (n) => {
    const el = $("#queueCount"), from = shown; shown = n;
    if (reduce || from === n) { el.textContent = n; return; }
    const t0 = performance.now();
    const step = (t) => { const p = Math.min(1, (t - t0) / 600); el.textContent = Math.round(from + (n - from) * p); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  };
  const pollCount = () => fetch("/api/queue/count").then((r) => r.json()).then((d) => countTo(d.waiting)).catch(() => {});
  pollCount(); setInterval(pollCount, 8000);

  /* ---------- booking chat ---------- */
  const log = $("#log"), form = $("#form"), input = $("#msg");
  const KEY = "sugar-chat-v1";
  const GREETING = "Hi love, welcome to Sugar Nails! 💅 Sugar is on a client right now, so I'll get you booked. What's your name?";
  let state = load() || fresh();
  let busy = false;

  function fresh() { return { messages: [{ role: "assistant", content: GREETING }], engine: null, order: null, booking: null }; }
  function load() { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {} }
  const scroll = () => requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });

  function bubble(role, text) {
    const d = document.createElement("div");
    d.className = "bubble " + (role === "user" ? "me" : "bot");
    d.textContent = text;
    log.appendChild(d); scroll();
    return d;
  }
  function typing() { const t = document.createElement("div"); t.className = "typing"; t.innerHTML = "<i></i><i></i><i></i>"; log.appendChild(t); scroll(); return t; }
  function clearChips() { log.querySelectorAll(".chips").forEach((c) => c.remove()); }

  function chips(list, multi) {
    clearChips();
    if (!list || !list.length) return;
    const wrap = document.createElement("div"); wrap.className = "chips";
    const picked = new Set();
    let send;
    list.forEach((label, i) => {
      const b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.style.setProperty("--i", i);
      b.innerHTML = (SHADES[label] ? `<span class="sw" style="background:${SHADES[label]}"></span>` : "") + label;
      b.addEventListener("click", () => {
        if (!multi) return userSays(label);
        picked.has(label) ? picked.delete(label) : picked.add(label);
        b.classList.toggle("on");
        send.disabled = !picked.size; send.textContent = picked.size ? `Send (${picked.size})` : "Pick one or more";
      });
      wrap.appendChild(b);
    });
    if (multi) {
      send = document.createElement("button"); send.type = "button"; send.className = "chip send-multi"; send.disabled = true;
      send.textContent = "Pick one or more"; send.style.setProperty("--i", list.length);
      send.addEventListener("click", () => picked.size && userSays([...picked].join(", ")));
      wrap.appendChild(send);
    }
    log.appendChild(wrap); scroll();
  }

  const SVC_LABEL = {}, STYLE_LABEL = {}, LEN_LABEL = {};
  fetch("/api/menu").then((r) => r.json()).then((m) => {
    m.services.forEach((s) => SVC_LABEL[s.id] = [s.label, s.price]);
    m.styles.forEach((s) => STYLE_LABEL[s.id] = [s.label, s.price]);
    m.lengths.forEach((s) => LEN_LABEL[s.id] = [s.label, s.price]);
  });

  function orderCard(o) {
    const c = document.createElement("div"); c.className = "order-card";
    const rows = [];
    o.services.forEach((s) => rows.push([SVC_LABEL[s]?.[0] || s, SVC_LABEL[s] ? naira(SVC_LABEL[s][1]) : ""]));
    if (STYLE_LABEL[o.style]?.[1]) rows.push([STYLE_LABEL[o.style][0], "+" + naira(STYLE_LABEL[o.style][1])]);
    if (LEN_LABEL[o.length]?.[1] && o.services.some((s) => ["acrylic_full", "gelx", "press_on", "refill"].includes(s))) rows.push([LEN_LABEL[o.length][0] + " length", "+" + naira(LEN_LABEL[o.length][1])]);
    if (!STYLE_LABEL[o.style]?.[1] && o.style !== "plain") rows.push(["Style", STYLE_LABEL[o.style]?.[0] || o.style]);
    if (o.colours?.length && o.colours[0] !== "None") rows.push(["Colours", o.colours.join(", ")]);
    if (o.length && o.length !== "natural" && !rows.some((r) => r[0].endsWith(" length"))) rows.push(["Length", LEN_LABEL[o.length]?.[0] || o.length]);
    if (o.shape && o.shape !== "n/a") rows.push(["Shape", o.shape]);
    rows.push(["Notes", o.notes || "None"], ["Time", o.time], ["Name", o.name], ["Phone", o.phone]);
    c.innerHTML = `<h4>Your booking</h4>${rows.map(([a, b]) => `<div class="line"><span>${esc(a)}</span><span>${esc(b)}</span></div>`).join("")}
      <div class="total"><span>Total</span><b>${naira(o.total)}</b></div>
      <div class="actions"><button class="pill plum pay">Pay ${naira(o.total)}</button><button class="pill small change">Change something</button></div>`;
    c.querySelector(".pay").addEventListener("click", () => openPay(o));
    c.querySelector(".change").addEventListener("click", () => userSays("I want to change something"));
    log.appendChild(c); scroll();
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));

  function render() {
    log.innerHTML = ""; $("#chat").classList.remove("booked");
    state.messages.forEach((m) => bubble(m.role, m.display || m.content));
    if (state.booking) return showTicket(state.booking, false);
    if (state.order) orderCard(state.order);
    else if (state.lastChips) chips(state.lastChips, state.lastMulti);
  }

  async function userSays(text) {
    text = String(text).trim();
    if (!text || busy) return;
    if (state.booking) return;
    busy = true; clearChips();
    log.querySelectorAll(".order-card").forEach((c) => c.remove());
    state.order = null;
    state.messages.push({ role: "user", content: text }); bubble("user", text); save();
    const t = typing(); const t0 = performance.now();
    let data;
    try {
      const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: state.messages.map(({ role, content }) => ({ role, content })), engine: state.engine }) });
      data = await r.json();
    } catch { data = { text: "Network wahala 😅 Please check your connection and send that again.", chips: [] }; state.messages.pop(); }
    const wait = Math.max(0, 650 - (performance.now() - t0));
    await new Promise((res) => setTimeout(res, reduce ? 0 : wait));
    t.remove();
    if (data.engine === "fallback" && state.messages.length > 3) state.engine = "fallback";
    // keep the raw reply (with chips / order) in history so the model sees exactly what it said
    const raw = data.text + (data.chips?.length ? `\n[${data.multi ? "multi" : "chips"}: ${data.chips.join(" | ")}]` : "") +
      (data.order ? "\n<order>" + JSON.stringify(stripOrder(data.order)) + "</order>" : "");
    let shown = data.text;
    if (data.order) { const ls = data.text.split("\n").filter(Boolean); shown = ls.length > 2 ? ls[0] + "\n" + ls[ls.length - 1] : data.text; }
    state.messages.push({ role: "assistant", content: raw, display: shown });
    bubble("assistant", shown);
    state.lastChips = data.chips; state.lastMulti = data.multi;
    if (data.order) { state.order = data.order; orderCard(data.order); } else chips(data.chips, data.multi);
    save(); busy = false; input.focus({ preventScroll: true });
  }
  function stripOrder(o) { const { booking_id, model_total, ...rest } = o; return rest; }

  form.addEventListener("submit", (e) => { e.preventDefault(); const v = input.value; input.value = ""; userSays(v); });
  $("#restart").addEventListener("click", () => { if (busy) return; stopPoll(); state = fresh(); save(); render(); });

  /* ---------- payment ---------- */
  const sheet = $("#sheet"); let paying = null;
  async function openPay(o) {
    paying = o;
    const r = await fetch("/api/pay/init", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ booking_id: o.booking_id }) });
    const d = await r.json();
    if (d.paid) return paid(o.booking_id);
    if (d.mode === "paystack" && d.authorization_url) { location.href = d.authorization_url; return; }
    $("#payAmount").textContent = naira(o.total);
    $("#payProg").style.display = "none"; $("#payProg i").style.width = "0";
    $("#payNow").disabled = false; $("#payNow").textContent = "Pay " + naira(o.total);
    sheet.classList.add("open");
  }
  document.querySelectorAll(".pay-method").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".pay-method").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); });
  }));
  $("#payCancel").addEventListener("click", () => sheet.classList.remove("open"));
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.classList.remove("open"); });
  $("#payNow").addEventListener("click", async () => {
    if (!paying) return;
    $("#payNow").disabled = true; $("#payNow").textContent = "Processing…";
    $("#payProg").style.display = "block"; requestAnimationFrame(() => $("#payProg i").style.width = "100%");
    await new Promise((r) => setTimeout(r, reduce ? 200 : 1500));
    const r = await fetch("/api/pay/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ booking_id: paying.booking_id }) });
    if (r.ok) { sheet.classList.remove("open"); paid(paying.booking_id); }
    else { $("#payNow").disabled = false; $("#payNow").textContent = "Try again"; }
  });

  function paid(id) {
    state.booking = id; state.order = null; save();
    log.querySelectorAll(".order-card,.chips").forEach((c) => c.remove());
    showTicket(id, true);
  }

  let pollT = null;
  const stopPoll = () => { clearInterval(pollT); pollT = null; };
  function showTicket(id, celebrate) {
    const t = document.createElement("div"); t.className = "ticket";
    t.innerHTML = `<svg class="check" viewBox="0 0 90 90"><circle cx="45" cy="45" r="40" fill="none" stroke="#d9697f" stroke-width="5"/>
      <path d="M27 46l12 12 24-26" fill="none" stroke="#6e1f2e" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <h4>You're booked!</h4><div class="pos-label">Your place in Sugar's queue</div><div class="pos" id="tPos">…</div>
      <div class="status-line" id="tStatus">Payment received. We'll text you when you're next.</div>
      <button class="pill small" id="newBooking" style="margin-top:14px">Book for someone else</button><div class="confetti"></div>`;
    log.appendChild(t); $("#chat").classList.add("booked");
    const pin = () => { log.style.scrollBehavior = "auto"; log.scrollTop = log.scrollHeight; log.style.scrollBehavior = ""; };
    requestAnimationFrame(pin); [250, 700, 1200].forEach((ms) => setTimeout(pin, ms));
    t.querySelector("#newBooking").addEventListener("click", () => { stopPoll(); state = fresh(); save(); render(); });
    if (celebrate && !reduce) {
      const cf = t.querySelector(".confetti"), cols = Object.values(SHADES);
      for (let i = 0; i < 34; i++) {
        const p = document.createElement("i");
        p.style.left = Math.random() * 100 + "%"; p.style.background = cols[i % cols.length];
        p.style.setProperty("--x", (Math.random() * 160 - 80) + "px"); p.style.setProperty("--r", (Math.random() * 720 - 360) + "deg");
        p.style.animationDelay = Math.random() * 0.4 + "s"; cf.appendChild(p);
      }
    }
    const upd = async () => {
      try {
        const d = await (await fetch("/api/booking/" + id)).json();
        const pos = t.querySelector("#tPos"), st = t.querySelector("#tStatus");
        if (d.status === "in_chair") { pos.textContent = "Now"; st.textContent = "Sugar is ready for you. Come on in! 💅"; }
        else if (d.status === "done") { pos.textContent = "✓"; st.textContent = "All done. Thank you for choosing Sugar Nails!"; stopPoll(); }
        else if (d.position) { if (pos.textContent !== "#" + d.position) { pos.textContent = "#" + d.position; pos.animate?.([{ transform: "scale(1.25)" }, { transform: "none" }], { duration: 450, easing: "cubic-bezier(.34,1.56,.64,1)" }); }
          st.textContent = d.position === 1 ? "You're next! Please head over." : `${d.position - 1} ${d.position - 1 === 1 ? "person" : "people"} ahead of you.`; }
      } catch {}
    };
    upd(); stopPoll(); pollT = setInterval(upd, 4000);
  }

  // returning from Paystack checkout
  const qp = new URLSearchParams(location.search).get("booking");
  if (qp) { state.booking = qp; state.order = null; save(); history.replaceState(null, "", location.pathname + "#book"); }
  render();
})();
