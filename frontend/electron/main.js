/**
 * KingIn Electron Main Process — Production Desktop App
 *
 * Architecture:
 *   Electron spawns KingIn_v2.exe (PyInstaller backend) as a child process,
 *   waits for it to respond on port 8000, then loads the pre-built React
 *   dashboard from disk via the app:// custom protocol.
 *
 * Features:
 *   - Splash screen while backend starts
 *   - System tray with show/hide/quit
 *   - Single-instance lock
 *   - Custom frameless window
 *   - IPC bridge (renderer → backend API)
 *   - Window position/size persistence
 *   - Native OS notifications on trade signals
 *   - Keyboard shortcut (Ctrl+Shift+K) to toggle window
 */

const {
  app, BrowserWindow, ipcMain, protocol, net,
  Tray, Menu, Notification, globalShortcut, nativeImage, shell
} = require('electron');
const path   = require('path');
const fs     = require('fs');
const http   = require('http');
const { spawn } = require('child_process');

// ── Single instance lock ──────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) { app.quit(); process.exit(0); }

// ── Globals ───────────────────────────────────────────────────────────
let mainWindow   = null;
let splashWindow = null;
let tray         = null;
let pyProc       = null;
let LOG_PATH     = null;
let windowState  = { width: 1440, height: 900 };

const IS_DEV   = !app.isPackaged;
const APP_DIR  = app.getAppPath();
const DATA_DIR = app.getPath('userData');

// Paths to the bundled backend exe
function backendExePath() {
  if (IS_DEV) {
    // Dev mode: use the exe from root dist/
    return path.join(APP_DIR, '..', 'dist', 'KingIn_v2.exe');
  }
  // Packaged: extraResources puts it in resources/backend/
  return path.join(process.resourcesPath, 'backend', 'KingIn_v2.exe');
}

function licensePath() {
  if (IS_DEV) {
    return path.join(APP_DIR, '..', 'license.kingin');
  }
  return path.join(process.resourcesPath, 'backend', 'license.kingin');
}

// ── Logging ───────────────────────────────────────────────────────────
function initLog() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  LOG_PATH = path.join(DATA_DIR, 'kingin.log');
  try {
    const stat = fs.statSync(LOG_PATH);
    if (stat.size > 5 * 1024 * 1024) fs.renameSync(LOG_PATH, LOG_PATH + '.old');
  } catch (_) {}
}

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { if (LOG_PATH) fs.appendFileSync(LOG_PATH, line); } catch (_) {}
  console.log(msg);
}

// ── Window state persistence ─────────────────────────────────────────
function loadWindowState() {
  const p = path.join(DATA_DIR, 'window-state.json');
  try {
    if (fs.existsSync(p)) windowState = { ...windowState, ...JSON.parse(fs.readFileSync(p, 'utf8')) };
  } catch (_) {}
}

function saveWindowState() {
  if (!mainWindow) return;
  const b = mainWindow.getBounds();
  try {
    fs.writeFileSync(
      path.join(DATA_DIR, 'window-state.json'),
      JSON.stringify({ x: b.x, y: b.y, width: b.width, height: b.height })
    );
  } catch (_) {}
}

// ── Splash screen ─────────────────────────────────────────────────────
function createSplash() {
  splashWindow = new BrowserWindow({
    width: 480, height: 300,
    frame: false, transparent: true,
    alwaysOnTop: true, resizable: false,
    skipTaskbar: true, center: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  const html = `<!DOCTYPE html><html><head><style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{width:480px;height:300px;background:#0B0E14;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:20px;font-family:'Segoe UI',sans-serif;
    color:white;border-radius:16px;overflow:hidden;border:1px solid rgba(93,95,239,.25)}
    .logo{font-size:36px;font-weight:900;letter-spacing:.5em;
    background:linear-gradient(135deg,#C9A84C,#F5D98C);-webkit-background-clip:text;
    -webkit-text-fill-color:transparent}
    .sub{font-size:10px;color:#6B7280;letter-spacing:.3em;text-transform:uppercase}
    .bar{width:200px;height:2px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden}
    .fill{height:100%;background:linear-gradient(90deg,#C9A84C,#F5D98C);animation:load 2.5s ease-in-out infinite}
    @keyframes load{0%{width:0}60%{width:80%}100%{width:100%}}
    .status{font-size:10px;color:#6B7280;letter-spacing:.12em}
    .ver{position:absolute;bottom:14px;right:20px;font-size:9px;color:#333}
  </style></head><body>
    <div class="logo">KINGIN</div>
    <div class="sub">Institutional Trading System</div>
    <div class="bar"><div class="fill"></div></div>
    <div class="status">Starting backend engine…</div>
    <div class="ver">v2.0.0</div>
  </body></html>`;

  splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
}

function closeSplash() {
  if (splashWindow) { splashWindow.close(); splashWindow = null; }
}

// ── Main window ───────────────────────────────────────────────────────
function createMainWindow() {
  loadWindowState();

  mainWindow = new BrowserWindow({
    x: windowState.x, y: windowState.y,
    width: windowState.width, height: windowState.height,
    minWidth: 1000, minHeight: 650,
    frame: false,
    backgroundColor: '#0B0E14',
    icon: getIconPath(),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,  // Allow loading local files
    },
  });

  mainWindow.once('ready-to-show', () => {
    closeSplash();
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.on('close', (e) => {
    // Minimize to tray instead of closing
    if (tray && !app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    } else {
      saveWindowState();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });

  // Load the pre-built React dashboard
  const indexPath = IS_DEV
    ? path.join(APP_DIR, 'dist', 'index.html')
    : path.join(APP_DIR, 'dist', 'index.html');

  log(`[MAIN] Loading: ${indexPath}`);
  mainWindow.loadFile(indexPath);
}

// ── System Tray ───────────────────────────────────────────────────────
function createTray() {
  const iconPath = getIconPath();
  let icon;
  if (iconPath && fs.existsSync(iconPath)) {
    icon = nativeImage.createFromPath(iconPath);
    icon = icon.resize({ width: 16, height: 16 });
  } else {
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);
  tray.setToolTip('KingIn Trading System v2.0');

  const menu = Menu.buildFromTemplate([
    { label: 'KingIn Trading System', enabled: false },
    { type: 'separator' },
    { label: 'Show Dashboard', click: () => {
      if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
      else createMainWindow();
    }},
    { label: 'Hide to Tray', click: () => mainWindow?.hide() },
    { type: 'separator' },
    { label: 'Open Log File', click: () => {
      if (LOG_PATH && fs.existsSync(LOG_PATH)) shell.openPath(LOG_PATH);
    }},
    { type: 'separator' },
    { label: 'Quit KingIn', click: () => {
      app.isQuitting = true;
      if (pyProc) try { pyProc.kill(); } catch (_) {}
      app.quit();
    }},
  ]);
  tray.setContextMenu(menu);

  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
    else createMainWindow();
  });
}

// ── Icon helper ───────────────────────────────────────────────────────
function getIconPath() {
  const candidates = [
    path.join(APP_DIR, 'its_icon.ico'),
    path.join(APP_DIR, 'its_icon.png'),
    path.join(APP_DIR, '..', 'its_icon.ico'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

// ── Backend process ───────────────────────────────────────────────────
function startBackend() {
  const exe = backendExePath();
  log(`[BACKEND] Exe path: ${exe}`);

  if (!fs.existsSync(exe)) {
    log(`[BACKEND] WARNING: Backend exe not found at ${exe}`);
    log('[BACKEND] The dashboard will load without a live backend.');
    return;
  }

  // Kill anything on port 8000 first
  try {
    require('child_process').execSync(
      'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :8000 ^| findstr LISTENING\') do taskkill /f /pid %a',
      { stdio: 'ignore', shell: true }
    );
  } catch (_) {}

  const cwd = path.dirname(exe);

  // Copy license file next to exe if not there
  const licSrc = licensePath();
  const licDst = path.join(cwd, 'license.kingin');
  if (fs.existsSync(licSrc) && !fs.existsSync(licDst)) {
    try { fs.copyFileSync(licSrc, licDst); } catch (_) {}
  }

  log(`[BACKEND] Spawning: ${exe}`);
  pyProc = spawn(exe, [], { cwd, stdio: 'pipe', detached: false });

  pyProc.stdout.on('data', d => log(`[PY] ${d.toString().trim()}`));
  pyProc.stderr.on('data', d => log(`[PY] ${d.toString().trim()}`));
  pyProc.on('exit', code => log(`[PY EXIT] code=${code}`));
  pyProc.on('error', err => log(`[PY ERROR] ${err.message}`));
}

function waitForBackend(maxMs = 45000, interval = 1500) {
  return new Promise(resolve => {
    const start = Date.now();
    const check = () => {
      const req = http.request(
        { hostname: '127.0.0.1', port: 8000, path: '/health', method: 'GET', timeout: 1000 },
        res => { res.resume(); log('[BACKEND] Healthy!'); resolve(true); }
      );
      req.on('error', () => {
        if (Date.now() - start < maxMs) setTimeout(check, interval);
        else { log('[BACKEND] Timeout — proceeding anyway'); resolve(false); }
      });
      req.end();
    };
    check();
  });
}

// ── IPC: API bridge ────────────────────────────────────────────────────
function setupIPC() {
  // Forward API requests to Python backend
  ipcMain.handle('api-request', async (_, { method, url, data, headers = {} }) => {
    const payload = data ? JSON.stringify(data) : null;
    const options = {
      hostname: '127.0.0.1', port: 8000,
      path: url.startsWith('/') ? url : `/${url}`,
      method: method.toUpperCase(),
      headers: {
        'Content-Type': 'application/json',
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      },
      timeout: 10000,
    };
    return new Promise(resolve => {
      const req = http.request(options, res => {
        let body = '';
        res.on('data', c => body += c);
        res.on('end', () => {
          try { resolve({ status: res.statusCode, data: JSON.parse(body) }); }
          catch (_) { resolve({ status: res.statusCode, data: body }); }
        });
      });
      req.on('error', e => resolve({ status: 500, data: { error: e.message } }));
      req.on('timeout', () => { req.destroy(); resolve({ status: 504, data: { error: 'timeout' } }); });
      if (payload) req.write(payload);
      req.end();
    });
  });

  // Window controls (custom titlebar)
  ipcMain.on('win-minimize', () => mainWindow?.minimize());
  ipcMain.on('win-maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize();
    else mainWindow?.maximize();
  });
  ipcMain.on('win-close', () => mainWindow?.close());
  ipcMain.on('win-hide',  () => mainWindow?.hide());

  // Trade signal → native OS notification
  ipcMain.on('trade-signal', (_, signal) => {
    if (Notification.isSupported()) {
      new Notification({
        title: `KingIn — ${signal.action || 'SIGNAL'}`,
        body: `${signal.symbol || 'XAUUSD'} @ ${signal.price || '—'}`,
        silent: false,
      }).show();
    }
  });

  // Open log file
  ipcMain.on('open-log', () => {
    if (LOG_PATH && fs.existsSync(LOG_PATH)) shell.openPath(LOG_PATH);
  });
}

// ── Keyboard shortcuts ────────────────────────────────────────────────
function setupShortcuts() {
  globalShortcut.register('CommandOrControl+Shift+K', () => {
    if (mainWindow?.isVisible()) mainWindow.hide();
    else { mainWindow?.show(); mainWindow?.focus(); }
  });
}

// ── Second instance handler ───────────────────────────────────────────
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

// ── App lifecycle ─────────────────────────────────────────────────────
app.whenReady().then(async () => {
  initLog();
  log('=== KINGIN DESKTOP APP STARTING ===');

  setupIPC();
  createSplash();
  startBackend();

  log('[MAIN] Waiting for backend...');
  await waitForBackend();

  createMainWindow();
  createTray();
  setupShortcuts();

  log('[MAIN] Ready.');
});

app.on('window-all-closed', () => {
  // Don't quit — keep in tray
});

app.on('before-quit', () => {
  app.isQuitting = true;
  globalShortcut.unregisterAll();
  saveWindowState();
  if (pyProc) {
    try { pyProc.kill(); } catch (_) {}
    pyProc = null;
  }
});

app.on('activate', () => {
  if (!mainWindow) createMainWindow();
  else mainWindow.show();
});
