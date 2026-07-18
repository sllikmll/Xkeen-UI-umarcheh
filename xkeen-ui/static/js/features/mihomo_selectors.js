let initialized = false;
let loading = false;
let lastData = null;

const SELECTOR_TYPES = new Set(['Selector', 'Fallback', 'URLTest', 'LoadBalance']);

function $(id) { return document.getElementById(id); }

function csrfToken() {
  try {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? String(meta.getAttribute('content') || '') : '';
  } catch (e) { return ''; }
}

async function fetchJson(url, options = {}) {
  const headers = Object.assign({ 'Accept': 'application/json' }, options.headers || {});
  const method = String(options.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    const csrf = csrfToken();
    if (csrf) headers['X-CSRF-Token'] = csrf;
  }
  const response = await fetch(url, Object.assign({ cache: 'no-store' }, options, { headers }));
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    const msg = data.error || data.message || ('HTTP ' + response.status);
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

function setText(id, text, cls) {
  const el = $(id);
  if (!el) return;
  el.textContent = text || '';
  if (cls) el.className = cls;
}

function delayBadge(delay) {
  if (delay === null || delay === undefined || delay === '') return '<span class="xk-delay xk-delay-muted">—</span>';
  const n = Number(delay);
  const cls = !n ? 'bad' : (n < 300 ? 'good' : (n < 700 ? 'warn' : 'bad'));
  return `<span class="xk-delay xk-delay-${cls}">${n} ms</span>`;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function nodeLabel(nodesByName, name) {
  const p = nodesByName.get(name) || {};
  const type = p.type ? String(p.type) : '';
  const alive = p.alive === false ? 'offline' : (p.alive === true ? 'online' : '');
  return `<span class="xk-node-name">${esc(name)}</span><span class="xk-node-meta">${esc(type)} ${alive ? '· ' + alive : ''}</span>${delayBadge(p.delay)}`;
}

async function selectProxy(selector, name) {
  setText('mihomo-selectors-status', `Переключаю ${selector} → ${name}…`);
  await fetchJson('/api/mihomo/clash/proxies/' + encodeURIComponent(selector), {
    method: 'PUT',
    body: JSON.stringify({ name })
  });
  await loadSelectors();
}

function renderSelectors(data) {
  const list = $('mihomo-selectors-list');
  if (!list) return;
  const selectors = Array.isArray(data.selectors) ? data.selectors : [];
  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  const nodesByName = new Map();
  [...selectors, ...nodes].forEach((p) => nodesByName.set(String(p.name || ''), p));

  setText('mihomo-selectors-summary', `Групп: ${selectors.length} · узлов/служебных proxy: ${nodes.length} · controller: ${data.controller || 'n/a'}`);

  if (!selectors.length) {
    list.innerHTML = '<div class="status">Mihomo API ответил, но selector-группы не найдены.</div>';
    return;
  }

  list.innerHTML = selectors.map((sel) => {
    const name = String(sel.name || '');
    const now = String(sel.now || '');
    const all = Array.isArray(sel.all) ? sel.all.map(String) : [];
    const options = all.map((item) => {
      const active = item === now;
      return `<button type="button" class="xk-proxy-choice ${active ? 'active' : ''}" data-selector="${esc(name)}" data-proxy="${esc(item)}">${nodeLabel(nodesByName, item)}</button>`;
    }).join('');
    const auto = SELECTOR_TYPES.has(String(sel.type || '')) && String(sel.type || '') !== 'Selector';
    return `
      <article class="xk-selector-card">
        <div class="xk-selector-card-head">
          <div>
            <div class="xk-selector-title">${esc(name)}</div>
            <div class="xk-selector-sub">${esc(sel.type || '')}${auto ? ' · авто-группа' : ''}</div>
          </div>
          <div class="xk-selector-current">Сейчас: <b>${esc(now || '—')}</b></div>
        </div>
        <div class="xk-proxy-grid">${options}</div>
      </article>`;
  }).join('');

  list.querySelectorAll('.xk-proxy-choice').forEach((btn) => {
    btn.addEventListener('click', () => {
      const selector = btn.getAttribute('data-selector') || '';
      const proxy = btn.getAttribute('data-proxy') || '';
      if (!selector || !proxy || btn.classList.contains('active')) return;
      selectProxy(selector, proxy).catch((error) => {
        setText('mihomo-selectors-status', 'Ошибка: ' + error.message);
      });
    });
  });
}

export async function loadSelectors() {
  if (loading) return;
  loading = true;
  setText('mihomo-selectors-status', 'Загрузка…');
  try {
    const data = await fetchJson('/api/mihomo/clash/proxies');
    lastData = data;
    renderSelectors(data);
    setText('mihomo-selectors-status', 'OK');
  } catch (error) {
    setText('mihomo-selectors-status', 'Ошибка: ' + error.message);
    const list = $('mihomo-selectors-list');
    if (list) list.innerHTML = `<div class="error">${esc(error.message)}</div>`;
  } finally {
    loading = false;
  }
}

function normalizeManualText(text) {
  const raw = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  if (!raw) return 'payload:\n';
  if (raw.startsWith('payload:')) return raw + '\n';
  const lines = raw.split('\n').map((line) => line.trim()).filter((line) => line && !line.startsWith('#'));
  return 'payload:\n' + lines.map((line) => '  - ' + line.replace(/^[-\s]+/, '')).join('\n') + '\n';
}

async function loadManual() {
  setText('mihomo-manual-status', 'Загрузка…');
  try {
    const data = await fetchJson('/api/mihomo/manual-proxy');
    const editor = $('mihomo-manual-editor');
    if (editor) editor.value = data.content || 'payload:\n';
    setText('mihomo-manual-path', data.path || '/opt/etc/mihomo/rules/manual-proxy.yaml');
    setText('mihomo-manual-status', 'OK');
  } catch (error) {
    setText('mihomo-manual-status', 'Ошибка: ' + error.message);
  }
}

async function saveManual() {
  const editor = $('mihomo-manual-editor');
  const content = editor ? editor.value : '';
  setText('mihomo-manual-status', 'Сохранение…');
  try {
    const data = await fetchJson('/api/mihomo/manual-proxy', {
      method: 'POST',
      body: JSON.stringify({ content })
    });
    if (editor) editor.value = data.content || content;
    setText('mihomo-manual-status', data.backup ? ('Сохранено · backup: ' + data.backup) : 'Сохранено');
  } catch (error) {
    setText('mihomo-manual-status', 'Ошибка: ' + error.message);
  }
}

export function initMihomoSelectorsPanel() {
  if (initialized) return;
  initialized = true;
  const refresh = $('mihomo-selectors-refresh-btn');
  if (refresh) refresh.addEventListener('click', () => loadSelectors());
  const loadBtn = $('mihomo-manual-load-btn');
  if (loadBtn) loadBtn.addEventListener('click', () => loadManual());
  const saveBtn = $('mihomo-manual-save-btn');
  if (saveBtn) saveBtn.addEventListener('click', () => saveManual());
  const normBtn = $('mihomo-manual-normalize-btn');
  if (normBtn) normBtn.addEventListener('click', () => {
    const editor = $('mihomo-manual-editor');
    if (editor) editor.value = normalizeManualText(editor.value);
  });
  loadManual();
  loadSelectors();
}

export function onShowMihomoSelectorsPanel() {
  initMihomoSelectorsPanel();
  if (!lastData) loadSelectors();
}
