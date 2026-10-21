import fs from 'node:fs';
import axe from 'axe-core';
import { JSDOM } from 'jsdom';

const STATIC = new URL('../../src/planner/static/', import.meta.url);
const read = (url) => fs.readFileSync(url, 'utf8');
export const fixture = (name) =>
  JSON.parse(read(new URL(`fixtures/${name}.json`, import.meta.url)));

export const reply = (data, status = 200) => ({
  ok: status < 400,
  status,
  headers: { get: () => null },
  json: async () => structuredClone(data),
  blob: async () => new Blob(['BEGIN:VCALENDAR']),
});

/** Loads the real index.html and app.js into jsdom with a stubbed network. */
export function loadApp(routes) {
  const html = read(new URL('index.html', STATIC)).replace(/<script[^>]*><\/script>/, '');
  const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'http://localhost/' });
  const { window } = dom;
  const calls = [];
  window.fetch = async (path, init) => {
    calls.push({ path, body: init?.body ? JSON.parse(init.body) : null });
    const route = routes[path];
    if (!route) throw new Error(`unexpected request ${path}`);
    return route();
  };
  window.print = () => {};
  window.eval(read(new URL('app.js', STATIC)));
  return { window, document: window.document, calls };
}

export const settle = (ms = 30) => new Promise((resolve) => setTimeout(resolve, ms));

export function submit(window) {
  window.document.querySelector('#plan-form')
    .dispatchEvent(new window.Event('submit', { cancelable: true }));
}

/** Runs axe-core; colour contrast is checked separately (jsdom has no layout). */
export async function accessibilityViolations(window) {
  window.eval(axe.source);
  const results = await window.axe.run(window.document, {
    rules: { 'color-contrast': { enabled: false } },
  });
  return [...results.violations].map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(' | ')}`);
}
