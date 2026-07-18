let initialized = false;
let loading = false;
let lastData = null;
let viewMode = 'tiles';

const VIEW_MODE_KEY = 'xkeen.mihomo.selectors.viewMode';
const SELECTOR_TYPES = new Set(['Selector', 'Fallback', 'URLTest', 'LoadBalance']);
const NO_DELAY_TYPES = new Set(['Reject', 'RejectDrop', 'Dns', 'Pass', 'Relay', 'Compatible']);

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

function delayClass(delay) {
  if (delay === null || delay === undefined || delay === '') return 'muted';
  const n = Number(delay);
  return !n ? 'bad' : (n < 300 ? 'good' : (n < 700 ? 'warn' : 'bad'));
}

function delayText(delay) {
  if (delay === null || delay === undefined || delay === '') return 'ping';
  const n = Number(delay);
  return Number.isFinite(n) ? `${n} ms` : 'ping';
}

function delayBadge(name, delay, enabled = true) {
  const cls = delayClass(delay);
  const label = delayText(delay);
  const dis = enabled ? '' : ' disabled';
  const title = enabled ? 'Нажми, чтобы обновить ping этого узла' : 'Ping для этого типа недоступен';
  return `<span class="xk-delay xk-delay-${cls} ${enabled ? 'xk-delay-clickable' : ''}" role="button" tabindex="0" title="${esc(title)}" data-delay-proxy="${esc(name)}"${dis}>${esc(label)}</span>`;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function isDelayCapable(proxy) {
  if (!proxy) return true;
  const type = String(proxy.type || '');
  if (NO_DELAY_TYPES.has(type)) return false;
  if (type.toLowerCase() === 'selector' && Array.isArray(proxy.all) && proxy.all.length) return true;
  return true;
}

function nodeLabel(nodesByName, name) {
  const p = nodesByName.get(name) || {};
  const type = p.type ? String(p.type) : '';
  const alive = p.alive === false ? 'offline' : (p.alive === true ? 'online' : '');
  const canDelay = isDelayCapable(p);
  return `<span class="xk-node-name">${esc(name)}</span><span class="xk-node-meta">${esc(type)} ${alive ? '· ' + alive : ''}</span>${delayBadge(name, p.delay, canDelay)}`;
}

function setProxyDelayInData(name, delay) {
  if (!lastData) return;
  const lists = [lastData.selectors, lastData.nodes];
  lists.forEach((list) => {
    if (!Array.isArray(list)) return;
    list.forEach((item) => {
      if (String(item.name || '') === String(name)) item.delay = delay;
    });
  });
}

function updateDelayDom(name, delay, ok = true) {
  const cls = delayClass(delay);
  document.querySelectorAll(`[data-delay-proxy="${CSS.escape(String(name))}"]`).forEach((el) => {
    el.className = `xk-delay xk-delay-${ok ? cls : 'bad'} xk-delay-clickable`;
    el.textContent = ok ? delayText(delay) : 'fail';
    el.title = ok ? 'Нажми, чтобы обновить ping этого узла' : 'Ping не прошёл — нажми, чтобы повторить';
  });
}

async function pingProxy(name) {
  const proxy = String(name || '').trim();
  if (!proxy) return;
  setText('mihomo-selectors-status', `Пингую ${proxy}…`);
  document.querySelectorAll(`[data-delay-proxy="${CSS.escape(proxy)}"]`).forEach((el) => {
    el.classList.add('is-loading');
    el.textContent = '…';
  });
  try {
    const data = await fetchJson('/api/mihomo/clash/proxies/' + encodeURIComponent(proxy) + '/delay', {
      method: 'POST',
      body: JSON.stringify({ timeout: 5000 })
    });
    setProxyDelayInData(proxy, data.delay);
    updateDelayDom(proxy, data.delay, true);
    setText('mihomo-selectors-status', `${proxy}: ${delayText(data.delay)}`);
  } catch (error) {
    updateDelayDom(proxy, null, false);
    setText('mihomo-selectors-status', `${proxy}: ошибка ping — ${error.message}`);
  } finally {
    document.querySelectorAll(`[data-delay-proxy="${CSS.escape(proxy)}"]`).forEach((el) => el.classList.remove('is-loading'));
  }
}

function collectPingNames() {
  const names = [];
  const seen = new Set();
  document.querySelectorAll('[data-delay-proxy]').forEach((el) => {
    if (el.hasAttribute('disabled')) return;
    const name = String(el.getAttribute('data-delay-proxy') || '').trim();
    if (!name || seen.has(name)) return;
    seen.add(name);
    names.push(name);
  });
  return names;
}

async function pingAll() {
  const btn = $('mihomo-selectors-ping-all-btn');
  const names = collectPingNames();
  if (!names.length) {
    setText('mihomo-selectors-status', 'Нет узлов для ping');
    return;
  }
  if (btn) btn.disabled = true;
  setText('mihomo-selectors-status', `Обновляю ping: ${names.length} узлов…`);
  document.querySelectorAll('[data-delay-proxy]').forEach((el) => {
    if (!el.hasAttribute('disabled')) {
      el.classList.add('is-loading');
      el.textContent = '…';
    }
  });
  try {
    const data = await fetchJson('/api/mihomo/clash/proxies/delay-all', {
      method: 'POST',
      body: JSON.stringify({ names, timeout: 5000, workers: 6 })
    });
    let okCount = 0;
    const results = Array.isArray(data.results) ? data.results : [];
    results.forEach((item) => {
      const name = String(item.proxy || '');
      if (!name) return;
      if (item.ok) okCount += 1;
      setProxyDelayInData(name, item.delay);
      updateDelayDom(name, item.delay, !!item.ok);
    });
    setText('mihomo-selectors-status', `Ping обновлён: ${okCount}/${results.length}`);
  } catch (error) {
    setText('mihomo-selectors-status', 'Ошибка массового ping: ' + error.message);
  } finally {
    document.querySelectorAll('[data-delay-proxy]').forEach((el) => el.classList.remove('is-loading'));
    if (btn) btn.disabled = false;
  }
}

async function selectProxy(selector, name) {
  setText('mihomo-selectors-status', `Переключаю ${selector} → ${name}…`);
  await fetchJson('/api/mihomo/clash/proxies/' + encodeURIComponent(selector), {
    method: 'PUT',
    body: JSON.stringify({ name })
  });
  await loadSelectors();
}

function selectorOptionLabel(nodesByName, name) {
  const p = nodesByName.get(name) || {};
  const type = p.type ? String(p.type) : '';
  const delay = delayText(p.delay);
  const alive = p.alive === false ? 'offline' : (p.alive === true ? 'online' : '');
  const bits = [name];
  if (delay !== 'ping') bits.push(delay);
  if (type) bits.push(type);
  if (alive) bits.push(alive);
  return bits.join(' · ');
}

function setViewMode(mode) {
  viewMode = mode === 'list' ? 'list' : 'tiles';
  try { window.localStorage.setItem(VIEW_MODE_KEY, viewMode); } catch (e) {}
  document.querySelectorAll('[data-view-mode]').forEach((btn) => {
    const active = String(btn.getAttribute('data-view-mode') || '') === viewMode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  if (lastData) renderSelectors(lastData);
}

function loadViewModePreference() {
  try {
    const saved = String(window.localStorage.getItem(VIEW_MODE_KEY) || '').trim();
    viewMode = saved === 'list' ? 'list' : 'tiles';
  } catch (e) {
    viewMode = 'tiles';
  }
}

function renderTiles(selectors, nodesByName) {
  return selectors.map((sel) => {
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
}

function renderListMode(selectors, nodesByName) {
  return `
    <div class="xk-selector-list-mode">
      ${selectors.map((sel) => {
        const name = String(sel.name || '');
        const now = String(sel.now || '');
        const all = Array.isArray(sel.all) ? sel.all.map(String) : [];
        const current = nodesByName.get(now) || {};
        const currentDelay = delayBadge(now, current.delay, isDelayCapable(current));
        const opts = all.map((item) => {
          const selected = item === now ? ' selected' : '';
          return `<option value="${esc(item)}"${selected}>${esc(selectorOptionLabel(nodesByName, item))}</option>`;
        }).join('');
        return `
          <article class="xk-selector-row">
            <div class="xk-selector-row-title">
              <div class="xk-selector-title">${esc(name)}</div>
              <div class="xk-selector-sub">${esc(sel.type || '')}</div>
            </div>
            <select class="xk-selector-select" data-selector-select="${esc(name)}" aria-label="Выбор proxy для ${esc(name)}">
              ${opts}
            </select>
            <div class="xk-selector-row-current" title="Текущий выбранный proxy">
              <span>${esc(now || '—')}</span>
              ${now ? currentDelay : ''}
            </div>
          </article>`;
      }).join('')}
    </div>`;
}

function bindSelectorEvents(list) {
  list.querySelectorAll('.xk-proxy-choice').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      if (event.target && event.target.closest && event.target.closest('[data-delay-proxy]')) return;
      const selector = btn.getAttribute('data-selector') || '';
      const proxy = btn.getAttribute('data-proxy') || '';
      if (!selector || !proxy || btn.classList.contains('active')) return;
      selectProxy(selector, proxy).catch((error) => {
        setText('mihomo-selectors-status', 'Ошибка: ' + error.message);
      });
    });
  });

  list.querySelectorAll('[data-selector-select]').forEach((select) => {
    select.addEventListener('change', () => {
      const selector = select.getAttribute('data-selector-select') || '';
      const proxy = select.value || '';
      if (!selector || !proxy) return;
      select.disabled = true;
      selectProxy(selector, proxy).catch((error) => {
        setText('mihomo-selectors-status', 'Ошибка: ' + error.message);
      }).finally(() => {
        select.disabled = false;
      });
    });
  });

  list.querySelectorAll('[data-delay-proxy]').forEach((badge) => {
    const handler = (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (badge.hasAttribute('disabled')) return;
      const proxy = badge.getAttribute('data-delay-proxy') || '';
      pingProxy(proxy);
    };
    badge.addEventListener('click', handler);
    badge.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') handler(event);
    });
  });
}

function renderSelectors(data) {
  const list = $('mihomo-selectors-list');
  if (!list) return;
  const selectors = Array.isArray(data.selectors) ? data.selectors : [];
  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  const nodesByName = new Map();
  [...selectors, ...nodes].forEach((p) => nodesByName.set(String(p.name || ''), p));

  setText('mihomo-selectors-summary', `Групп: ${selectors.length} · узлов/служебных proxy: ${nodes.length} · controller: ${data.controller || 'n/a'}`);
  document.querySelectorAll('[data-view-mode]').forEach((btn) => {
    const active = String(btn.getAttribute('data-view-mode') || '') === viewMode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  if (!selectors.length) {
    list.className = 'xk-selectors-list';
    list.innerHTML = '<div class="status">Mihomo API ответил, но selector-группы не найдены.</div>';
    return;
  }

  list.className = viewMode === 'list' ? 'xk-selectors-list xk-selectors-list-compact' : 'xk-selectors-list';
  list.innerHTML = viewMode === 'list' ? renderListMode(selectors, nodesByName) : renderTiles(selectors, nodesByName);
  bindSelectorEvents(list);
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
  loadViewModePreference();
  document.querySelectorAll('[data-view-mode]').forEach((btn) => {
    btn.addEventListener('click', () => setViewMode(btn.getAttribute('data-view-mode') || 'tiles'));
  });
  setViewMode(viewMode);
  const refresh = $('mihomo-selectors-refresh-btn');
  if (refresh) refresh.addEventListener('click', () => loadSelectors());
  const pingAllBtn = $('mihomo-selectors-ping-all-btn');
  if (pingAllBtn) pingAllBtn.addEventListener('click', () => pingAll());
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
