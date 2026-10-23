// Celebration Planner front end. No dependencies, no innerHTML: every piece
// of server data is inserted with textContent, so it can never run as markup.
'use strict';

const $ = (selector) => document.querySelector(selector);
const form = $('#plan-form');
const output = $('#plan-output');
const statusBox = $('#status');
const errorBox = $('#errors');
const submitButton = $('#submit');
const resultsHeading = $('#results');
const MAX_PRIORITIES = 3;
const REQUEST_TIMEOUT_MS = 30000;

/** Creates an element; strings become text nodes (never markup). */
function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === false || value == null) continue;
    if (key === 'class') node.className = value;
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function isoToDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

const formatDate = (iso) =>
  isoToDate(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

const formatMoney = (amount, currency) =>
  new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);

function relativeDays(days) {
  if (days === 0) return 'today';
  if (days < 0) return `${-days} days after the event`;
  return days === 1 ? 'tomorrow' : `in ${days} days`;
}

function setStatus(text) {
  statusBox.textContent = text;
}

function showErrors(messages) {
  errorBox.replaceChildren(
    h('strong', {}, 'Please check the following:'),
    h('ul', {}, messages.map((m) => h('li', {}, m))),
  );
  errorBox.hidden = false;
}

function clearErrors() {
  errorBox.hidden = true;
  errorBox.replaceChildren();
}

function readPayload() {
  const data = new FormData(form);
  const text = (name) => (data.get(name) ?? '').toString().trim();
  const payload = {
    event_type: text('event_type'),
    title: text('title'),
    event_date: text('event_date'),
    guest_count: Number(text('guest_count')),
    budget: Number(text('budget')),
    currency: text('currency'),
    setting: text('setting'),
    dietary: data.getAll('dietary'),
    priorities: data.getAll('priorities'),
  };
  for (const name of ['city', 'cultural_style', 'theme_preferences', 'notes']) {
    if (text(name)) payload[name] = text(name);
  }
  if (payload.event_type === 'birthday' && text('honoree_age') !== '') {
    payload.honoree_age = Number(text('honoree_age'));
  }
  return payload;
}

async function postJson(path, payload) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

async function describeFailure(response) {
  if (response.status === 429) {
    const wait = response.headers.get('Retry-After');
    return [`Too many requests. Please try again${wait ? ` in ${wait} seconds` : ' shortly'}.`];
  }
  let body = null;
  try { body = await response.json(); } catch { /* not JSON */ }
  if (body && Array.isArray(body.errors)) {
    return body.errors.map((e) => `${e.field}: ${e.message}`);
  }
  if (body && typeof body.detail === 'string') return [body.detail];
  return ['Something went wrong. Please try again.'];
}

// ---------- rendering ----------

function renderSummary(plan) {
  const stat = (label, value) => h('div', {}, h('dt', {}, label), h('dd', {}, value));
  return h('section', { class: 'card', 'aria-labelledby': 'sum-h' },
    h('h3', { id: 'sum-h' }, plan.title),
    h('dl', { class: 'stats' },
      stat('Event date', formatDate(plan.event_date)),
      stat('Time to go', plan.days_to_go === 0 ? 'Today' : `${plan.days_to_go} days`),
      stat('Per guest', formatMoney(plan.budget_per_guest, plan.currency)),
      stat('Budget style', plan.tier),
    ),
    plan.advisories.map((a) =>
      h('p', { class: `advisory ${a.level}` }, a.level === 'warning' ? 'Heads up: ' : 'Tip: ', a.message)),
  );
}

function renderBudget(plan) {
  const rows = plan.budget.map((line) => {
    const fill = h('span', { class: 'fill' });
    fill.style.width = `${Math.min(100, line.percent)}%`; // CSSOM, allowed by CSP
    return h('tr', {},
      h('th', { scope: 'row' }, line.label),
      h('td', {}, `${line.percent}%`, h('span', { class: 'bar', 'aria-hidden': 'true' }, fill)),
      h('td', { class: 'num' }, formatMoney(line.amount, plan.currency)),
      h('td', { class: 'note' }, line.note),
    );
  });
  return h('section', { class: 'card', 'aria-labelledby': 'bud-h' },
    h('h3', { id: 'bud-h' }, 'Budget'),
    h('div', { class: 'table-wrap' },
      h('table', {},
        h('caption', {}, `Total ${formatMoney(plan.total_budget, plan.currency)}`),
        h('thead', {}, h('tr', {},
          h('th', { scope: 'col' }, 'Category'), h('th', { scope: 'col' }, 'Share'),
          h('th', { scope: 'col' }, 'Amount'), h('th', { scope: 'col' }, 'Why'))),
        h('tbody', {}, rows))));
}

function renderTimeline(plan) {
  const progress = h('p', { id: 'progress', 'aria-live': 'polite' });
  const total = plan.timeline.length;
  const update = () => {
    const done = document.querySelectorAll('.rail input:checked').length;
    progress.textContent = `${done} of ${total} done`;
  };
  const items = plan.timeline.map((item) => {
    const box = h('input', { type: 'checkbox', id: `t-${item.key}` });
    const li = h('li', { class: item.urgent ? 'urgent' : '' },
      h('label', { for: `t-${item.key}` }, box,
        h('span', {},
          h('span', { class: 'when' }, formatDate(item.due_date),
            h('span', { class: 'note' }, ` · ${relativeDays(item.days_until)}`),
            item.urgent && h('span', { class: 'tag' }, 'Due soon'),
            item.critical && !item.urgent && h('span', { class: 'tag' }, 'Critical')),
          h('span', { class: 'what' }, item.label))));
    box.addEventListener('change', () => { li.classList.toggle('done', box.checked); update(); });
    return li;
  });
  const section = h('section', { class: 'card', 'aria-labelledby': 'tl-h' },
    h('h3', { id: 'tl-h' }, 'Timeline'),
    plan.timeline_compressed && h('p', { class: 'note' }, 'Dates are compressed to fit the time you have.'),
    progress,
    h('ol', { class: 'rail' }, items),
    h('div', { class: 'actions' },
      h('button', { type: 'button', id: 'ics' }, 'Add to calendar (.ics)'),
      h('button', { type: 'button', class: 'secondary', id: 'print' }, 'Print this plan')));
  update();
  return section;
}

function renderVendors(plan) {
  const list = (items) => h('ul', {}, items.map((t) => h('li', {}, t)));
  return h('section', { class: 'card', 'aria-labelledby': 'ven-h' },
    h('h3', { id: 'ven-h' }, 'Vendor checklist'),
    plan.vendors.map((v) =>
      h('details', {},
        h('summary', {}, `${v.name} · book by ${formatDate(v.book_by)} · about ${formatMoney(v.estimated_budget, plan.currency)}`),
        h('h4', {}, 'To do'), list(v.tasks),
        h('h4', {}, 'Ask them'), list(v.questions))));
}

function renderIdeasPlaceholder() {
  return h('section', { class: 'card', id: 'ideas', 'aria-labelledby': 'ide-h', 'aria-busy': 'true' },
    h('h3', { id: 'ide-h' }, 'Ideas for your day'),
    h('p', { class: 'note', id: 'ideas-note' }, 'Finding ideas that fit your guests…'));
}

function fillIdeas(data) {
  const { ideas, ideas_source: source } = data;
  const section = $('#ideas');
  const group = (title, items) => items.length > 0 && h('div', {},
    h('h4', {}, title), h('ul', {}, items.map((i) => h('li', {}, i))));
  section.replaceChildren(
    h('h3', { id: 'ide-h' }, 'Ideas for your day'),
    h('p', { class: 'note' }, source === 'gemini'
      ? 'Suggested by AI (Gemini). Please check details with your vendors before booking.'
      : 'Curated suggestions matched to your answers.'),
    h('dl', { class: 'theme' }, ideas.themes.flatMap((t) => [h('dt', {}, t.name), h('dd', {}, t.description)])),
    group('Activities', ideas.activities),
    group('Menu', ideas.menu),
    group('Personal touches', ideas.personal_touches),
    group('Ways to save', ideas.savings_tips));
  section.setAttribute('aria-busy', 'false');
}

function renderMethod() {
  return h('details', { class: 'card method' },
    h('summary', {}, 'How this plan was made'),
    h('ul', {},
      h('li', {}, 'Calculated by fixed rules: the budget split, dates, checklists and vendor questions. The same answers always give the same result.'),
      h('li', {}, 'Suggested by AI: themes, activities, menu and personal touches. If AI is unavailable you get curated ideas instead.'),
      h('li', {}, 'These are estimates, not quotes. Nothing is booked or sent for you, and your answers are not stored.')));
}

async function loadIdeas(payload) {
  try {
    const response = await postJson('/api/ideas', payload);
    if (!response.ok) throw new Error('ideas unavailable');
    fillIdeas(await response.json());
    setStatus('Ideas are ready.');
  } catch {
    $('#ideas-note').textContent = 'Ideas are unavailable right now. Your plan above is complete.';
    $('#ideas').setAttribute('aria-busy', 'false');
  }
}

async function downloadCalendar(payload, button) {
  button.disabled = true;
  try {
    const response = await postJson('/api/plan.ics', payload);
    if (!response.ok) { showErrors(await describeFailure(response)); return; }
    const url = URL.createObjectURL(await response.blob());
    const link = h('a', { href: url, download: 'celebration-timeline.ics' });
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setStatus('Calendar file downloaded.');
  } catch {
    showErrors(['Could not download the calendar. Please try again.']);
  } finally {
    button.disabled = false;
  }
}

function render(plan, payload) {
  output.replaceChildren(
    renderSummary(plan), renderBudget(plan), renderTimeline(plan),
    renderVendors(plan), renderIdeasPlaceholder(), renderMethod());
  $('#print').addEventListener('click', () => window.print());
  $('#ics').addEventListener('click', (e) => downloadCalendar(payload, e.currentTarget));
  setStatus(`Your plan is ready: ${plan.timeline.length} milestones and ${plan.vendors.length} vendor checklists. Ideas are loading.`);
  resultsHeading.focus();
}

// ---------- events ----------

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearErrors();
  const payload = readPayload();
  submitButton.disabled = true;
  output.setAttribute('aria-busy', 'true');
  setStatus('Building your plan…');
  try {
    const response = await postJson('/api/plan', payload);
    if (!response.ok) {
      setStatus('');
      showErrors(await describeFailure(response));
      resultsHeading.focus();
      return;
    }
    render(await response.json(), payload);
    loadIdeas(payload);
  } catch {
    setStatus('');
    showErrors(['We could not reach the server. Check your connection and try again.']);
    resultsHeading.focus();
  } finally {
    submitButton.disabled = false;
    output.removeAttribute('aria-busy');
  }
});

function syncEventType() {
  const type = new FormData(form).get('event_type');
  $('#age-field').hidden = type !== 'birthday';
}

function limitPriorities() {
  const boxes = [...document.querySelectorAll('#priorities input')];
  const full = boxes.filter((b) => b.checked).length >= MAX_PRIORITIES;
  for (const box of boxes) box.disabled = full && !box.checked;
}

function setMinimumDate() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  $('#event_date').min = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

const EXAMPLES = {
  wedding: {
    event_type: 'wedding', title: 'Priya and Arjun’s wedding', daysAhead: 150, guest_count: 250,
    budget: 1800000, currency: 'INR', setting: 'outdoor', dietary: ['vegetarian', 'jain'],
    priorities: ['food', 'decor'], city: 'Ongole', cultural_style: 'Telugu',
  },
  birthday: {
    event_type: 'birthday', title: 'Anu turns 5', daysAhead: 30, guest_count: 25,
    budget: 30000, currency: 'INR', setting: 'indoor', dietary: ['nut_free'],
    priorities: ['entertainment'], honoree_age: 5, theme_preferences: 'space and rockets',
  },
  community: {
    event_type: 'community', title: 'Colony Diwali Mela', daysAhead: 45, guest_count: 300,
    budget: 150000, currency: 'INR', setting: 'outdoor', dietary: ['vegetarian'],
    priorities: ['food', 'entertainment'], cultural_style: 'Telugu',
  },
};

function isoDateAhead(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function applyExample(key) {
  const example = EXAMPLES[key];
  form.reset();
  const radio = form.querySelector(`input[name=event_type][value=${example.event_type}]`);
  radio.checked = true;
  for (const name of ['title', 'guest_count', 'budget', 'currency', 'setting', 'city',
    'cultural_style', 'theme_preferences', 'honoree_age']) {
    if (example[name] !== undefined) form.elements[name].value = example[name];
  }
  form.elements.event_date.value = isoDateAhead(example.daysAhead);
  for (const box of form.querySelectorAll('#dietary input, #priorities input')) {
    box.checked = (example[box.name] ?? []).includes(box.value);
  }
  syncEventType();
  limitPriorities();
  clearErrors();
  setStatus('Example loaded. Review the details, then choose Create my plan.');
  $('#title').focus();
}

for (const button of document.querySelectorAll('[data-example]')) {
  button.addEventListener('click', () => applyExample(button.dataset.example));
}

form.addEventListener('change', (e) => {
  if (e.target.name === 'event_type') syncEventType();
  if (e.target.name === 'priorities') limitPriorities();
});
setMinimumDate();
syncEventType();
