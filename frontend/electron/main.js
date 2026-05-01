const { app, BrowserWindow, ipcMain, protocol, net } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const url = require('url');

// Register app scheme to bypass file:// CORS for ES Modules
protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { secure: true, standard: true, supportFetchAPI: true, corsEnabled: true } }
]);

// ── Fix #21: Use userData path — never C:\ root (fails on UAC-restricted systems) ──
let LOG_PATH;
try {
  LOG_PATH = path.join(app.getPath('userData'), 'kingin_debug.log');
} catch (_) {
  LOG_PATH = path.join(__dirname, 'kingin_debug.log');
}

function logToDisk(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync(LOG_PATH, line); } catch (e) {}
}

let mainWindow;
let pyProc = null;

function startPython() {
  logToDisk('--- STARTING BACKEND ---');
  const isDev = !app.isPackaged;
  const script = isDev
    ? path.join(__dirname, '..', '..', 'backend', 'kingin_api.py')
    : path.join(process.resourcesPath, 'backend', 'kingin_api.py');

  const spawnArgs = [script];
  const spawnOpts = { stdio: 'pipe', cwd: path.dirname(script) };

  // ── Fix #20: Kill previous process before retrying to avoid port conflicts ──
  const trySpawn = (cmd) => {
    if (pyProc && pyProc.exitCode === null) {
      logToDisk(`[SPAWN] Killing previous process before retry with ${cmd}`);
      try { pyProc.kill(); } catch (_) {}
    }

    logToDisk(`[SPAWN] Attempting: ${cmd} ${script}`);
    const proc = spawn(cmd, spawnArgs, spawnOpts);
    pyProc = proc;

    proc.stdout.on('data', (d) => logToDisk(`[PY STDOUT] ${d.toString().trim()}`));
    proc.stderr.on('data', (d) => logToDisk(`[PY STDERR] ${d.toString().trim()}`));
    proc.on('exit', (code) => logToDisk(`[PY EXIT] Code: ${code}`));

    proc.on('error', (err) => {
      logToDisk(`[SPAWN ERROR] ${cmd} failed: ${err.message}`);
      if (cmd === 'python') trySpawn('python3');
      else if (cmd === 'python3') trySpawn('py');
      else logToDisk('[FATAL] No Python interpreter found. Please install Python 3.10+');
    });

    return proc;
  };

  pyProc = trySpawn('python');
}

/**
 * Polls port 8088 until the backend responds, then resolves.
 * Times out after maxWaitMs milliseconds.
 */
function waitForBackend(maxWaitMs = 60000, intervalMs = 2000) {
  return new Promise((resolve) => {
    const start = Date.now();
    const check = () => {
      const req = http.request(
        { hostname: '127.0.0.1', port: 8088, path: '/api/system/status', method: 'GET', timeout: 1000 },
        (res) => { res.resume(); resolve(); }
      );
      req.on('error', () => {
        if (Date.now() - start < maxWaitMs) {
          setTimeout(check, intervalMs);
        } else {
          logToDisk('[WARN] Backend did not start within timeout — proceeding anyway');
          resolve();
        }
      });
      req.end();
    };
    check();
  });
}

/**
 * Make a single HTTP request to the Python backend.
 * Forwards all headers from the renderer (Authorization, X-Control-Token).
 */
function httpRequest(options, payload) {
  return new Promise((resolve) => {
    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', (c) => body += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(body) }); }
        catch (e) { resolve({ status: res.statusCode, data: body }); }
      });
    });
    req.on('error', (e) => resolve({ status: 500, error: e.message, data: { success: false, error: e.message } }));
    if (payload) req.write(payload);
    req.end();
  });
}

app.whenReady().then(async () => {
  // Auto-start backend only in production (packaged) mode.
  // In dev mode, `npm run dev:api` manages the backend separately.
  if (app.isPackaged) {
    startPython();
    logToDisk('[MAIN] Waiting for backend to become ready...');
    await waitForBackend();
    logToDisk('[MAIN] Backend is ready.');
  }

  ipcMain.handle('api-request', async (event, args) => {
    const { method, url: reqUrl, data, headers: clientHeaders = {} } = args;
    const payload = data ? (typeof data === 'string' ? data : JSON.stringify(data)) : null;

    // Forward auth headers from the renderer so the backend validates them correctly
    const options = {
      hostname: '127.0.0.1', port: 8088,
      path: reqUrl.startsWith('/api/') ? reqUrl : `/api${reqUrl.startsWith('/') ? reqUrl : '/' + reqUrl}`,
      method: method.toUpperCase(),
      headers: {
        'Content-Type': 'application/json',
        // Propagate Authorization and X-Control-Token from the renderer request
        ...(clientHeaders.Authorization ? { Authorization: clientHeaders.Authorization } : {}),
        ...(clientHeaders['X-Control-Token'] ? { 'X-Control-Token': clientHeaders['X-Control-Token'] } : {}),
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      }
    };
    return httpRequest(options, payload);
  });

  // Handle app:// protocol to serve Vite files safely from the packaged dist/
  protocol.handle('app', (request) => {
    const reqUrl = new URL(request.url);
    let urlPath = reqUrl.pathname;
    if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
    const filePath = path.join(__dirname, '..', 'dist', urlPath);
    return net.fetch(url.pathToFileURL(filePath).href);
  });

  mainWindow = new BrowserWindow({
    width: 1440, height: 900,
    minWidth: 1024, minHeight: 680,
    backgroundColor: '#080B12',
    icon: path.join(__dirname, '..', 'its_icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    }
  });

  // ── Fix #19: Dev uses port 5173, matching Vite config and wait-on ──
  if (!app.isPackaged) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadURL('app://kingin/');
  }
});

app.on('window-all-closed', () => {
  if (pyProc && pyProc.exitCode === null) {
    try { pyProc.kill(); } catch (_) {}
  }
  app.quit();
});
