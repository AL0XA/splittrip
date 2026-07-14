// Тусовка & Траты — Telegram Mini App для деления общих расходов.
const tg = window.Telegram?.WebApp;
const INIT_DATA = tg?.initData || "";
const view = document.getElementById("view");

let current = null; // текущий открытый event detail

// ---------- API ----------
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": INIT_DATA,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------- Утилиты ----------
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function money(n, cur) {
  const v = Number(n).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  return `${v} ${cur || "₽"}`;
}

function toast(msg, isError = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = isError ? "error" : "";
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2800);
}

function haptic(type = "light") {
  try { tg?.HapticFeedback?.impactOccurred(type); } catch {}
}

// ---------- Экран: список событий ----------
async function renderHome() {
  current = null;
  view.innerHTML = `<div class="topbar"><h1>💸 Мои тусовки</h1></div>
    <div id="events" class="muted">Загрузка…</div>
    <button class="primary" id="create-btn" style="margin-top:14px">＋ Создать тусовку</button>`;
  document.getElementById("create-btn").onclick = showCreateSheet;

  try {
    const { events } = await api("/api/events");
    const box = document.getElementById("events");
    if (!events.length) {
      box.className = "";
      box.innerHTML = `<div class="empty"><div class="big">🎉</div>
        Пока нет ни одной тусовки.<br>Создай первую и позови друзей!</div>`;
      return;
    }
    box.className = "";
    box.innerHTML = events.map((e) => `
      <div class="card event-item" data-id="${e.id}">
        <div style="flex:1">
          <div class="title">${esc(e.title)}</div>
          <div class="sub">${e.member_count} участник(ов)</div>
        </div>
        <div class="chev">›</div>
      </div>`).join("");
    box.querySelectorAll(".event-item").forEach((el) =>
      (el.onclick = () => openEvent(el.dataset.id)));
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------- Экран: событие ----------
let activeTab = "expenses";

async function openEvent(id) {
  try {
    const data = await api(`/api/events/${id}`);
    current = data;
    renderEvent();
  } catch (e) {
    toast(e.message, true);
  }
}

function renderEvent() {
  const d = current;
  const cur = d.currency;

  const membersHtml = d.members.map((m) =>
    `<span class="chip">${esc(m.name)}${m.user_id === d.me_id ? " (вы)" : ""}</span>`).join("");

  const expensesHtml = d.expenses.length
    ? d.expenses.map((e) => `
        <div class="expense">
          <div class="icon">🧾</div>
          <div class="info">
            <div class="desc">${esc(e.description)}</div>
            <div class="meta">${esc(e.payer_name)} заплатил · на ${e.participant_count} чел.</div>
          </div>
          <div class="amount">${money(e.amount, cur)}</div>
          ${(e.payer_id === d.me_id || d.owner_id === d.me_id)
            ? `<button class="del" data-eid="${e.id}">🗑</button>` : ""}
        </div>`).join("")
    : `<div class="empty">Пока нет трат. Добавьте первую!</div>`;

  const settlementHtml = d.settlement.length
    ? d.settlement.map((t) => `
        <div class="transfer">
          <span class="who">${esc(t.from_name)}</span>
          <span class="arrow">→</span>
          <span class="who">${esc(t.to_name)}</span>
          <span class="sum">${money(t.amount, cur)}</span>
        </div>`).join("")
    : `<div class="empty">Все в расчёте 🎉</div>`;

  const balancesHtml = d.members.map((m) => {
    const cls = m.balance > 0.004 ? "pos" : m.balance < -0.004 ? "neg" : "zero";
    const sign = m.balance > 0.004 ? "+" : "";
    const txt = Math.abs(m.balance) < 0.005 ? "в расчёте" : sign + money(m.balance, cur);
    return `<div class="balance-line"><span>${esc(m.name)}</span><span class="${cls}">${txt}</span></div>`;
  }).join("");

  view.innerHTML = `
    <div class="topbar">
      <button class="back" id="back">‹ Назад</button>
      <div class="spacer"></div>
    </div>
    <h1>${esc(d.title)}</h1>
    <div class="card">
      <div class="row"><h2 style="margin:0">Участники (${d.members.length})</h2></div>
      <div class="members" style="margin-top:8px">${membersHtml}</div>
      <button class="secondary" id="invite" style="margin-top:12px">🔗 Пригласить друзей</button>
    </div>

    <div class="tabs">
      <button class="tab ${activeTab === "expenses" ? "active" : ""}" data-tab="expenses">Траты</button>
      <button class="tab ${activeTab === "summary" ? "active" : ""}" data-tab="summary">Итоги</button>
    </div>

    <div id="tab-body"></div>
    <button class="primary" id="add-expense" style="margin-top:14px">＋ Добавить трату</button>`;

  const body = document.getElementById("tab-body");
  body.innerHTML = activeTab === "expenses"
    ? `<div class="card">${expensesHtml}</div>`
    : `<div class="card"><h2 style="margin-top:0">Кто кому переводит</h2>${settlementHtml}</div>
       <div class="card"><h2 style="margin-top:0">Балансы</h2>${balancesHtml}</div>`;

  document.getElementById("back").onclick = renderHome;
  document.getElementById("invite").onclick = invite;
  document.getElementById("add-expense").onclick = showExpenseSheet;
  view.querySelectorAll(".tab").forEach((t) => (t.onclick = () => {
    activeTab = t.dataset.tab; renderEvent();
  }));
  body.querySelectorAll(".del").forEach((b) =>
    (b.onclick = () => deleteExpense(b.dataset.eid)));
}

// ---------- Действия ----------
function showCreateSheet() {
  openSheet(`
    <h1>Новая тусовка</h1>
    <label class="field">Название</label>
    <input id="ev-title" placeholder="Например: Поездка в горы" maxlength="100" autofocus>
    <button class="primary" id="ev-save">Создать</button>`, () => {
    document.getElementById("ev-save").onclick = async () => {
      const title = document.getElementById("ev-title").value.trim();
      if (!title) return toast("Введите название", true);
      try {
        const data = await api("/api/events", {
          method: "POST", body: JSON.stringify({ title }),
        });
        closeSheet();
        current = data; activeTab = "expenses"; renderEvent();
        haptic("medium");
      } catch (e) { toast(e.message, true); }
    };
  });
}

function showExpenseSheet() {
  const d = current;
  const payerOpts = d.members.map((m) =>
    `<option value="${m.user_id}" ${m.user_id === d.me_id ? "selected" : ""}>${esc(m.name)}</option>`).join("");
  const checks = d.members.map((m) => `
    <label class="check">
      <input type="checkbox" class="part" value="${m.user_id}" checked>
      <span>${esc(m.name)}</span>
    </label>`).join("");

  openSheet(`
    <h1>Новая трата</h1>
    <label class="field">Сумма (${d.currency})</label>
    <input id="ex-amount" type="text" inputmode="decimal" placeholder="0" autofocus>
    <label class="field">За что</label>
    <input id="ex-desc" placeholder="Например: продукты" maxlength="140">
    <label class="field">Кто платил</label>
    <select id="ex-payer">${payerOpts}</select>
    <label class="field">Делим между</label>
    <div class="check-list">${checks}</div>
    <button class="primary" id="ex-save" style="margin-top:12px">Добавить</button>`, () => {
    document.getElementById("ex-save").onclick = async () => {
      const amount = parseFloat(document.getElementById("ex-amount").value.replace(",", "."));
      const description = document.getElementById("ex-desc").value.trim();
      const payer_id = Number(document.getElementById("ex-payer").value);
      const participant_ids = [...document.querySelectorAll(".part:checked")].map((c) => Number(c.value));
      if (!amount || amount <= 0) return toast("Введите сумму", true);
      if (!description) return toast("Укажите, за что", true);
      if (!participant_ids.length) return toast("Выберите участников", true);
      try {
        const data = await api(`/api/events/${current.id}/expenses`, {
          method: "POST",
          body: JSON.stringify({ amount, description, payer_id, participant_ids }),
        });
        closeSheet();
        current = data; renderEvent();
        haptic("medium");
      } catch (e) { toast(e.message, true); }
    };
  });
}

async function deleteExpense(eid) {
  if (!confirm("Удалить трату?")) return;
  try {
    current = await api(`/api/events/${current.id}/expenses/${eid}`, { method: "DELETE" });
    renderEvent();
  } catch (e) { toast(e.message, true); }
}

function invite() {
  const link = current.invite_link;
  if (link) {
    const text = `Присоединяйся к тусовке «${current.title}» и добавляй свои траты`;
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
    if (tg?.openTelegramLink) tg.openTelegramLink(url);
    else window.open(url, "_blank");
  } else {
    // BOT_USERNAME не задан на сервере — делимся кодом.
    toast(`Код приглашения: ${current.code}`);
  }
}

// ---------- Модалка (bottom sheet) ----------
function openSheet(html, onMount) {
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="sheet">${html}</div>`;
  ov.onclick = (e) => { if (e.target === ov) closeSheet(); };
  document.body.appendChild(ov);
  openSheet._ov = ov;
  onMount?.();
}
function closeSheet() {
  openSheet._ov?.remove();
  openSheet._ov = null;
}

// ---------- Инициализация ----------
async function init() {
  tg?.ready();
  tg?.expand();

  const startParam = tg?.initDataUnsafe?.start_param;
  if (startParam) {
    // Открыли по инвайт-ссылке — вступаем в событие и сразу открываем его.
    try {
      current = await api("/api/events/join", {
        method: "POST", body: JSON.stringify({ code: startParam }),
      });
      activeTab = "expenses";
      renderEvent();
      return;
    } catch (e) {
      toast("Не удалось присоединиться: " + e.message, true);
    }
  }
  renderHome();
}

init();
