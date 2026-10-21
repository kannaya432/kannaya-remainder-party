import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  accessibilityViolations, fixture, loadApp, reply, settle, submit,
} from './harness.mjs';

const okRoutes = () => ({
  '/api/plan': () => reply(fixture('plan')),
  '/api/ideas': () => reply(fixture('ideas')),
});

function fillValidForm(document) {
  document.querySelector('input[name=event_type][value=wedding]').checked = true;
  document.querySelector('#title').value = 'Test event';
  document.querySelector('#event_date').value = '2027-03-20';
  document.querySelector('#guest_count').value = '100';
  document.querySelector('#budget').value = '500000';
}

test('example buttons fill the form and show the birthday-only field', () => {
  const { document } = loadApp(okRoutes());
  document.querySelector('[data-example=birthday]').click();
  assert.equal(document.querySelector('input[name=event_type]:checked').value, 'birthday');
  assert.equal(document.querySelector('#age-field').hidden, false);
  assert.equal(document.querySelector('#honoree_age').value, '5');
  assert.match(document.querySelector('#status').textContent, /Example loaded/);
  document.querySelector('[data-example=wedding]').click();
  assert.equal(document.querySelector('#age-field').hidden, true);
});

test('priorities are limited to three', () => {
  const { document, window } = loadApp(okRoutes());
  for (const value of ['food', 'decor', 'venue', 'photography']) {
    const box = document.querySelector(`#priorities input[value=${value}]`);
    if (box.disabled) continue;
    box.checked = true;
    box.dispatchEvent(new window.Event('change', { bubbles: true }));
  }
  const checked = document.querySelectorAll('#priorities input:checked').length;
  const disabled = document.querySelectorAll('#priorities input:disabled').length;
  assert.equal(checked, 3);
  assert.equal(disabled, 3);
});

test('plan renders first, then ideas arrive and are announced', async () => {
  let releaseIdeas;
  const slowIdeas = new Promise((resolve) => { releaseIdeas = resolve; });
  const routes = okRoutes();
  routes['/api/ideas'] = async () => { await slowIdeas; return reply(fixture('ideas')); };
  const { window, document, calls } = loadApp(routes);
  fillValidForm(document);
  submit(window);
  await settle();

  assert.equal(document.querySelectorAll('.rail li').length, fixture('plan').timeline.length);
  assert.equal(document.querySelector('#ideas').getAttribute('aria-busy'), 'true');
  assert.equal(document.activeElement, document.querySelector('#results'));

  releaseIdeas();
  await settle();
  assert.equal(document.querySelector('#ideas').getAttribute('aria-busy'), 'false');
  assert.ok(document.querySelectorAll('#ideas li').length > 0);
  assert.equal(document.querySelector('#status').textContent, 'Ideas are ready.');
  assert.deepEqual(calls.map((c) => c.path), ['/api/plan', '/api/ideas']);
  assert.equal(calls[0].body.guest_count, 100);
});

test('checklist progress updates when items are ticked', async () => {
  const { window, document } = loadApp(okRoutes());
  fillValidForm(document);
  submit(window);
  await settle();
  const total = fixture('plan').timeline.length;
  assert.equal(document.querySelector('#progress').textContent, `0 of ${total} done`);
  document.querySelector('.rail input').click();
  assert.equal(document.querySelector('#progress').textContent, `1 of ${total} done`);
});

test('server text is never interpreted as markup', async () => {
  const hostile = '<img src=x onerror=alert(1)><script>alert(2)</script>';
  const plan = fixture('plan');
  plan.title = hostile;
  plan.budget[0].note = hostile;
  plan.timeline[0].label = hostile;
  plan.vendors[0].tasks[0] = hostile;
  const ideas = fixture('ideas');
  ideas.ideas.themes[0].name = hostile;
  ideas.ideas.menu[0] = hostile;
  const { window, document } = loadApp({
    '/api/plan': () => reply(plan),
    '/api/ideas': () => reply(ideas),
  });
  fillValidForm(document);
  submit(window);
  await settle();
  assert.equal(document.querySelectorAll('#plan-output img, #plan-output script').length, 0);
  assert.ok(document.querySelector('#plan-output').textContent.includes(hostile));
});

test('validation errors are shown in an alert region and focus moves to results', async () => {
  const { window, document } = loadApp({
    '/api/plan': () => reply({ errors: [{ field: 'event_date', message: 'The event date is in the past.' }] }, 422),
  });
  fillValidForm(document);
  submit(window);
  await settle();
  const box = document.querySelector('#errors');
  assert.equal(box.hidden, false);
  assert.equal(box.getAttribute('role'), 'alert');
  assert.match(box.textContent, /event_date: The event date is in the past/);
  assert.equal(document.activeElement, document.querySelector('#results'));
  assert.equal(document.querySelector('#submit').disabled, false);
});

test('a failed ideas call leaves the plan intact with a clear message', async () => {
  const routes = okRoutes();
  routes['/api/ideas'] = () => reply({ detail: 'boom' }, 500);
  const { window, document } = loadApp(routes);
  fillValidForm(document);
  submit(window);
  await settle();
  assert.ok(document.querySelectorAll('.rail li').length > 0);
  assert.match(document.querySelector('#ideas-note').textContent, /unavailable/);
  assert.equal(document.querySelector('#ideas').getAttribute('aria-busy'), 'false');
});

test('rate limiting shows a retry message', async () => {
  const limited = reply({ detail: 'Too many requests.' }, 429);
  limited.headers = { get: (name) => (name === 'Retry-After' ? '12' : null) };
  const { window, document } = loadApp({ '/api/plan': () => limited });
  fillValidForm(document);
  submit(window);
  await settle();
  assert.match(document.querySelector('#errors').textContent, /in 12 seconds/);
});

test('empty page and rendered results have no axe violations', async () => {
  const { window, document } = loadApp(okRoutes());
  assert.deepEqual(await accessibilityViolations(window), []);
  fillValidForm(document);
  submit(window);
  await settle();
  assert.deepEqual(await accessibilityViolations(window), []);
});
