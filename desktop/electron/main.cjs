const { app, BrowserWindow, dialog, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, spawnSync } = require('child_process');
const https = require('https');
const zlib = require('zlib');

const APP_NAME = 'Unified UI';
const MIHOMO_VERSION = '1.19.29';
const UI_PORT = Number(process.env.UNIFIED_UI_PORT || 18088);
const MIHOMO_PORT = Number(process.env.MIHOMO_CONTROLLER_PORT || 19090);
const MIXED_PORT = Number(process.env.MIHOMO_MIXED_PORT || 17890);
const DNS_PORT = Number(process.env.MIHOMO_DNS_PORT || 15353);
let enableTun = /^(1|true|yes|on)$/i.test(process.env.UNIFIED_UI_ENABLE_TUN || process.env.MIHOMO_ENABLE_TUN || '');

let win = null;
let backendProc = null;
let mihomoProc = null;
let elevatedMihomoPidFile = null;
let quitting = false;

function log(...args) {
  console.log('[desktop]', ...args);
}

function repoRoot() {
  // Packaged app is built with asar=false because the Python/Flask backend
  // must be launched from a real filesystem directory, not from app.asar.
  if (app.isPackaged) return app.getAppPath();
  return path.resolve(__dirname, '..', '..');
}

function resourcePath(...parts) {
  return path.join(repoRoot(), ...parts);
}

function runtimeRoot() {
  return path.join(app.getPath('userData'), 'runtime');
}

function desktopSettingsPath() {
  return path.join(app.getPath('userData'), 'desktop-settings.json');
}

function readDesktopSettings() {
  try {
    const file = desktopSettingsPath();
    if (!fs.existsSync(file)) return {};
    return JSON.parse(fs.readFileSync(file, 'utf8')) || {};
  } catch (_) {
    return {};
  }
}

function writeDesktopSettings(settings) {
  ensureDir(app.getPath('userData'));
  fs.writeFileSync(desktopSettingsPath(), `${JSON.stringify(settings, null, 2)}
`);
}

function loadDesktopRoutingSettings() {
  const settings = readDesktopSettings();
  if (typeof settings.enableTun === 'boolean') enableTun = settings.enableTun;
}


function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function existsExecutable(cmd) {
  const probe = spawnSync(cmd, ['--version'], { stdio: 'ignore' });
  return probe.status === 0;
}

function findPython() {
  const candidates = process.platform === 'win32'
    ? ['python.exe', 'py.exe']
    : ['python3', 'python'];
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, cmd === 'py.exe' ? ['-3', '--version'] : ['--version'], { encoding: 'utf8' });
    if (probe.status === 0) return { cmd, prefix: cmd === 'py.exe' ? ['-3'] : [] };
  }
  return null;
}

function runChecked(cmd, args, opts = {}) {
  log('run', cmd, args.join(' '));
  const res = spawnSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...opts });
  if (res.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed\nSTDOUT:\n${res.stdout || ''}\nSTDERR:\n${res.stderr || ''}`);
  }
  return res;
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function isRootLike() {
  return process.platform !== 'win32' && typeof process.getuid === 'function' && process.getuid() === 0;
}

function startMihomoElevatedDarwin(mihomo, mihomoDir, config, logsDir) {
  elevatedMihomoPidFile = path.join(runtimeRoot(), 'mihomo-elevated.pid');
  const logFile = path.join(logsDir, 'mihomo.log');
  fs.rmSync(elevatedMihomoPidFile, { force: true });
  const command = [
    shellQuote(mihomo),
    '-d', shellQuote(mihomoDir),
    '-f', shellQuote(config),
    '>>', shellQuote(logFile),
    '2>&1',
    '&',
    'echo $! >', shellQuote(elevatedMihomoPidFile),
  ].join(' ');
  log('requesting administrator privileges for Mihomo TUN mode');
  runChecked('osascript', ['-e', `do shell script ${JSON.stringify(command)} with administrator privileges`]);
  return null;
}

function stopElevatedMihomoDarwin() {
  if (!elevatedMihomoPidFile || !fs.existsSync(elevatedMihomoPidFile)) return;
  const pid = fs.readFileSync(elevatedMihomoPidFile, 'utf8').trim();
  if (!/^\d+$/.test(pid)) return;
  const command = `kill ${pid} 2>/dev/null || true`;
  try {
    runChecked('osascript', ['-e', `do shell script ${JSON.stringify(command)} with administrator privileges`]);
  } catch (err) {
    log('failed to stop elevated Mihomo:', err.message || err);
  }
}

function venvPython(venvDir) {
  if (process.platform === 'win32') return path.join(venvDir, 'Scripts', 'python.exe');
  return path.join(venvDir, 'bin', 'python');
}

function ensureVenv() {
  const rt = runtimeRoot();
  const venv = path.join(rt, 'venv');
  const py = venvPython(venv);
  const req = resourcePath('unified-ui', 'requirements.txt');
  if (!fs.existsSync(py)) {
    const found = findPython();
    if (!found) {
      throw new Error('Python 3 не найден. Установи Python 3.11+ и перезапусти Unified UI.');
    }
    ensureDir(rt);
    runChecked(found.cmd, [...found.prefix, '-m', 'venv', venv]);
    runChecked(py, ['-m', 'pip', 'install', '--upgrade', 'pip']);
  }
  const probe = spawnSync(py, ['-c', 'import flask, gevent, geventwebsocket'], { encoding: 'utf8' });
  if (probe.status !== 0) {
    runChecked(py, ['-m', 'pip', 'install', '--upgrade', 'pip']);
    runChecked(py, ['-m', 'pip', 'install', '-r', req]);
  }
  return py;
}

function platformMihomoAsset() {
  const arch = os.arch();
  if (process.platform === 'darwin') {
    if (arch === 'arm64') return { name: `mihomo-darwin-arm64-v${MIHOMO_VERSION}.gz`, bin: 'mihomo' };
    return { name: `mihomo-darwin-amd64-v${MIHOMO_VERSION}.gz`, bin: 'mihomo' };
  }
  if (process.platform === 'win32') {
    if (arch === 'arm64') return { name: `mihomo-windows-arm64-v${MIHOMO_VERSION}.zip`, bin: 'mihomo.exe' };
    return { name: `mihomo-windows-amd64-v${MIHOMO_VERSION}.zip`, bin: 'mihomo.exe' };
  }
  if (arch === 'arm64') return { name: `mihomo-linux-arm64-v${MIHOMO_VERSION}.gz`, bin: 'mihomo' };
  return { name: `mihomo-linux-amd64-v${MIHOMO_VERSION}.gz`, bin: 'mihomo' };
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close(); fs.rmSync(dest, { force: true });
        return download(res.headers.location, dest).then(resolve, reject);
      }
      if (res.statusCode !== 200) {
        file.close(); fs.rmSync(dest, { force: true });
        return reject(new Error(`download ${url} -> HTTP ${res.statusCode}`));
      }
      res.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', (err) => {
      file.close(); fs.rmSync(dest, { force: true }); reject(err);
    });
  });
}

async function ensureMihomo() {
  const rt = runtimeRoot();
  const binDir = path.join(rt, 'bin');
  ensureDir(binDir);
  const asset = platformMihomoAsset();
  const bin = path.join(binDir, asset.bin);
  if (fs.existsSync(bin)) return bin;
  const bundledArm64 = resourcePath('mikrotik', 'assets', 'mihomo-linux-arm64');
  if (process.platform === 'linux' && os.arch() === 'arm64' && fs.existsSync(bundledArm64)) {
    fs.copyFileSync(bundledArm64, bin);
    fs.chmodSync(bin, 0o755);
    return bin;
  }
  const tmp = path.join(rt, asset.name);
  const url = `https://github.com/MetaCubeX/mihomo/releases/download/v${MIHOMO_VERSION}/${asset.name}`;
  await download(url, tmp);
  if (asset.name.endsWith('.gz')) {
    const data = zlib.gunzipSync(fs.readFileSync(tmp));
    fs.writeFileSync(bin, data, { mode: 0o755 });
  } else if (asset.name.endsWith('.zip')) {
    // Windows zip extraction without extra dependencies: use PowerShell Expand-Archive.
    const out = path.join(rt, 'mihomo-zip');
    fs.rmSync(out, { recursive: true, force: true });
    ensureDir(out);
    runChecked('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', `Expand-Archive -Force ${JSON.stringify(tmp)} ${JSON.stringify(out)}`]);
    const found = fs.readdirSync(out).find((n) => n.toLowerCase().endsWith('.exe'));
    if (!found) throw new Error('mihomo.exe not found in downloaded archive');
    fs.copyFileSync(path.join(out, found), bin);
  }
  fs.rmSync(tmp, { force: true });
  return bin;
}

function tunConfigBlock() {
  if (!enableTun) return '';
  return `
tun:
  enable: true
  stack: system
  auto-route: true
  auto-detect-interface: true
  strict-route: false
  dns-hijack:
    - any:53
`;
}

function writeDefaultConfig(mihomoDir) {
  ensureDir(path.join(mihomoDir, 'rules'));
  ensureDir(path.join(mihomoDir, 'profiles'));
  const manual = path.join(mihomoDir, 'rules', 'manual-proxy.yaml');
  if (!fs.existsSync(manual)) fs.writeFileSync(manual, 'payload: []\n');
  const cfg = path.join(mihomoDir, 'config.yaml');
  if (fs.existsSync(cfg)) {
    if (enableTun) ensureTunInExistingConfig(cfg);
    return cfg;
  }
  fs.writeFileSync(cfg, `mixed-port: ${MIXED_PORT}
allow-lan: true
bind-address: 127.0.0.1
mode: rule
log-level: info
ipv6: false
external-controller: 127.0.0.1:${MIHOMO_PORT}
secret: ''
find-process-mode: off
profile:
  store-selected: true
  store-fake-ip: false
unified-delay: true
tcp-concurrent: true

${tunConfigBlock()}
dns:
  enable: true
  listen: 127.0.0.1:${DNS_PORT}
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver: [1.1.1.1, 8.8.8.8]
  nameserver: [https://1.1.1.1/dns-query, https://8.8.8.8/dns-query]

proxy-providers: {}

rule-providers:
  manual-proxy:
    type: file
    behavior: classical
    format: yaml
    path: ${manual.replace(/\\/g, '/')}

proxy-groups:
  - name: Маршрутизация
    type: select
    proxies: [DIRECT]
  - name: Ручной список
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: YouTube
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Telegram
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Meta
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: GitHub
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: AI
    type: select
    proxies: [DIRECT, Маршрутизация]
  - name: Остальное
    type: select
    proxies: [DIRECT, Маршрутизация]

rules:
  - RULE-SET,manual-proxy,Ручной список
  - DOMAIN-SUFFIX,ru,DIRECT
  - DOMAIN-SUFFIX,su,DIRECT
  - DOMAIN-SUFFIX,рф,DIRECT
  - DOMAIN-SUFFIX,youtube.com,YouTube
  - DOMAIN-SUFFIX,googlevideo.com,YouTube
  - DOMAIN-SUFFIX,ytimg.com,YouTube
  - DOMAIN-SUFFIX,telegram.org,Telegram
  - DOMAIN-SUFFIX,t.me,Telegram
  - DOMAIN-SUFFIX,facebook.com,Meta
  - DOMAIN-SUFFIX,instagram.com,Meta
  - DOMAIN-SUFFIX,github.com,GitHub
  - DOMAIN-SUFFIX,openai.com,AI
  - DOMAIN-SUFFIX,chatgpt.com,AI
  - MATCH,Остальное
`);
  return cfg;
}


function ensureTunInExistingConfig(cfg) {
  const text = fs.readFileSync(cfg, 'utf8');
  if (/^tun:\s*$/m.test(text)) return;
  const backup = `${cfg}.pre-tun-${Date.now()}.bak`;
  fs.copyFileSync(cfg, backup);
  const block = tunConfigBlock().trimEnd();
  fs.writeFileSync(cfg, `${block}

${text}`);
  log('TUN enabled in existing config, backup:', backup);
}

function warnTunPrivileges() {
  if (!enableTun) return;
  if (process.platform === 'darwin' && !isRootLike()) {
    log('TUN full-system routing is enabled. Mihomo will request macOS administrator privileges.');
    return;
  }
  if (process.platform !== 'win32' && !isRootLike()) {
    log('TUN is enabled, but the app is not running as root/admin. Mihomo may fail to create tun or add system routes.');
  } else {
    log('TUN full-system routing is enabled.');
  }
}

function waitFor(url, timeoutMs = 30000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      httpsOrHttpGet(url).then(resolve).catch((err) => {
        if (Date.now() - started > timeoutMs) reject(err);
        else setTimeout(tick, 500);
      });
    };
    tick();
  });
}

function httpsOrHttpGet(url) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https:') ? https : require('http');
    const req = mod.get(url, (res) => {
      res.resume();
      if (res.statusCode >= 200 && res.statusCode < 500) resolve(res.statusCode);
      else reject(new Error(`HTTP ${res.statusCode}`));
    });
    req.on('error', reject);
    req.setTimeout(2000, () => { req.destroy(new Error('timeout')); });
  });
}

async function startBackendStack() {
  const rt = runtimeRoot();
  const mihomoDir = path.join(rt, 'mihomo');
  const stateDir = path.join(rt, 'state');
  const logsDir = path.join(rt, 'logs');
  ensureDir(mihomoDir); ensureDir(stateDir); ensureDir(logsDir);
  const py = ensureVenv();
  const mihomo = await ensureMihomo();
  const config = writeDefaultConfig(mihomoDir);
  warnTunPrivileges();
  runChecked(mihomo, ['-t', '-d', mihomoDir, '-f', config]);
  if (enableTun && process.platform === 'darwin' && !isRootLike()) {
    mihomoProc = startMihomoElevatedDarwin(mihomo, mihomoDir, config, logsDir);
  } else {
    mihomoProc = spawn(mihomo, ['-d', mihomoDir, '-f', config], { stdio: ['ignore', fs.openSync(path.join(logsDir, 'mihomo.log'), 'a'), fs.openSync(path.join(logsDir, 'mihomo.log'), 'a')] });
  }
  const env = {
    ...process.env,
    UNIFIED_UI_PORT: String(UI_PORT),
    UNIFIED_UI_STATE_DIR: stateDir,
    UNIFIED_UI_DIR: stateDir,
    MIHOMO_CONFIG: config,
    MIHOMO_CONFIG_FILE: config,
    MIHOMO_ROOT: mihomoDir,
    MIHOMO_CONTROLLER_URL: `http://127.0.0.1:${MIHOMO_PORT}`,
    MIHOMO_CONTROLLER_HOST: '127.0.0.1',
    MIHOMO_CONTROLLER_PORT: String(MIHOMO_PORT),
    UNIFIED_UI_NAME: 'Unified UI Desktop',
    PYTHONUNBUFFERED: '1',
  };
  backendProc = spawn(py, [resourcePath('unified-ui', 'run_server.py')], {
    cwd: resourcePath('unified-ui'),
    env,
    stdio: ['ignore', fs.openSync(path.join(logsDir, 'ui.log'), 'a'), fs.openSync(path.join(logsDir, 'ui.log'), 'a')],
  });
  backendProc.on('exit', (code) => { if (!quitting) dialog.showErrorBox(APP_NAME, `Unified UI backend exited: ${code}`); });
  if (mihomoProc) {
    mihomoProc.on('exit', (code) => { if (!quitting) dialog.showErrorBox(APP_NAME, `Mihomo exited: ${code}`); });
  }
  await waitFor(`http://127.0.0.1:${UI_PORT}/`, 45000);
}


function installApplicationMenu() {
  const template = [
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    {
      label: 'Routing',
      submenu: [
        {
          label: 'Full-system TUN routing',
          type: 'checkbox',
          checked: enableTun,
          click: (item) => {
            const settings = readDesktopSettings();
            settings.enableTun = Boolean(item.checked);
            writeDesktopSettings(settings);
            dialog.showMessageBoxSync({
              type: 'info',
              title: APP_NAME,
              message: item.checked ? 'Full-system TUN routing включён.' : 'Full-system TUN routing выключен.',
              detail: 'Unified UI сейчас перезапустится. Для TUN на macOS будет системный запрос administrator privileges для Mihomo.',
            });
            app.relaunch();
            app.quit();
          },
        },
        { type: 'separator' },
        { label: 'Open runtime folder', click: () => shell.openPath(runtimeRoot()) },
      ],
    },
    { role: 'viewMenu' },
    { role: 'windowMenu' },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 980,
    minWidth: 1100,
    minHeight: 720,
    title: APP_NAME,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  win.loadURL(`http://127.0.0.1:${UI_PORT}/`);
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
}

function stopChildren() {
  quitting = true;
  for (const p of [backendProc, mihomoProc]) {
    if (p && !p.killed) {
      try { p.kill('SIGTERM'); } catch (_) {}
    }
  }
  if (process.platform === 'darwin') stopElevatedMihomoDarwin();
}

app.whenReady().then(async () => {
  try {
    loadDesktopRoutingSettings();
    installApplicationMenu();
    await startBackendStack();
    createWindow();
  } catch (err) {
    dialog.showErrorBox(APP_NAME, String(err && err.stack || err));
    app.quit();
  }
});

app.on('before-quit', stopChildren);
app.on('window-all-closed', () => app.quit());
