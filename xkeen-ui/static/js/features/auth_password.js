function $(sel, root = document) { return root.querySelector(sel); }
function setHidden(el, hidden) { if (el) el.classList.toggle('hidden', !!hidden); }
function getCsrf() {
  const input = $('#xk-password-form input[name="csrf_token"]');
  if (input && input.value) return input.value;
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') || '' : '';
}
function status(message, type = '') {
  const el = $('[data-xk-password-status]');
  if (!el) return;
  el.textContent = message || '';
  el.dataset.status = type || '';
}
function openModal() {
  const modal = $('#xk-password-modal');
  setHidden(modal, false);
  status('');
  setTimeout(() => $('#xk-password-form input[name="current_password"]')?.focus(), 20);
}
function closeModal() {
  const modal = $('#xk-password-modal');
  setHidden(modal, true);
  const form = $('#xk-password-form');
  if (form) form.reset();
  status('');
}
async function submitPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const btn = form.querySelector('button[type="submit"]');
  const payload = {
    current_password: form.current_password.value,
    new_password: form.new_password.value,
    new_password2: form.new_password2.value,
  };
  if (payload.new_password !== payload.new_password2) {
    status('Новые пароли не совпадают', 'error');
    return;
  }
  if ((payload.new_password || '').length < 8) {
    status('Новый пароль должен быть не короче 8 символов', 'error');
    return;
  }
  try {
    if (btn) btn.disabled = true;
    status('Сохраняю…', 'info');
    const res = await fetch('/api/auth/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrf() },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || data.error || `HTTP ${res.status}`);
    }
    status('Пароль изменён', 'success');
    setTimeout(closeModal, 700);
  } catch (error) {
    status(`Не удалось сменить пароль: ${error.message || error}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}
export function initAuthPasswordControls() {
  const btn = $('#xk-current-user-btn');
  const modal = $('#xk-password-modal');
  const form = $('#xk-password-form');
  if (!btn || !modal || !form || btn.dataset.xkPasswordWired) return;
  btn.dataset.xkPasswordWired = '1';
  btn.addEventListener('click', openModal);
  modal.querySelectorAll('[data-xk-password-close]').forEach((el) => el.addEventListener('click', closeModal));
  form.addEventListener('submit', submitPassword);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
  });
}
