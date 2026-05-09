import { app, BrowserWindow, ipcMain, protocol, net } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn, execSync } from 'child_process';
import http from 'http';
import url, { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Register app scheme to bypass file:// CORS for ES Modules
protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { secure: true, standard: true, supportFetchAPI: true, corsEnabled: true } }
]);

let LOG_PATH;

function initLogging() {
  try {
    const userData = app.getPath('userData');
    if (!fs.existsSync(userData)) {
      fs.mkdirSync(userData, { recursive: true });
    }
    LOG_PATH = path.join(userData, 'kingin_debug.log');
  } catch (_) {
    LOG_PATH = path.join(app.getAppPath(), 'kingin_debug.log');
  }
}

function logToDisk(msg) {
  if (!LOG_PATH) initLogging();
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync(LOG_PATH, line); } catch (e) {
    console.error(`Failed to log: ${e.message}`);
  }
}

let mainWindow;
let pyProc = null;

function startPython() {
  logToDisk('--- STARTING BACKEND ---');
  const isDev = !app.isPackaged;
  
  let script, cmd;
  if (isDev) {
    script = path.join(__dirname, '..', '..', 'backend', 'kingin_api.py');
    cmd = 'python';
  } else {
    // In production, we use the bundled kingin_api.exe (moved to resources/backend)
    const backendRoot = path.join(process.resourcesPath, 'backend');
    script = path.join(backendRoot, 'kingin_api.exe');
    cmd = script;
  }

  const spawnArgs = isDev ? [script] : [];
  const spawnOpts = { stdio: 'pipe', cwd: path.dirname(script) };

  // ── Port Cleanup: Ensure 8088 is free before starting ──
  // Synchronously kill any process using port 8088 to avoid race conditions
  const killExisting = () => {
    if (process.platform === 'win32') {
      try {
        execSync('for /f "tokens=5" %a in (\'netstat -aon ^| findstr :8088\') do taskkill /f /pid %a', { stdio: 'ignore' });
      } catch (e) {
        // Ignore errors if no process found
      }
    }
  };

  const trySpawn = (currentCmd) => {
    killExisting();
    logToDisk(`[SPAWN] Attempting: ${currentCmd}`);
    const proc = spawn(currentCmd, spawnArgs, spawnOpts);
    pyProc = proc;

    proc.stdout.on('data', (d) => logToDisk(`[PY STDOUT] ${d.toString().trim()}`));
    proc.stderr.on('data', (d) => logToDisk(`[PY STDERR] ${d.toString().trim()}`));
    proc.on('exit', (code) => logToDisk(`[PY EXIT] Code: ${code}`));

    proc.on('error', (err) => {
      logToDisk(`[SPAWN ERROR] ${currentCmd} failed: ${err.message}`);
      if (isDev) {
        if (currentCmd === 'python') trySpawn('python3');
        else if (currentCmd === 'python3') trySpawn('py');
        else logToDisk('[FATAL] No Python interpreter found. Please install Python 3.10+');
      } else {
        logToDisk(`[FATAL] Backend binary failed to start: ${err.message}`);
      }
    });

    return proc;
  };

  pyProc = trySpawn(cmd);
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
  initLogging();
  logToDisk('=== APP STARTING ===');

  // Handle app:// protocol to serve Vite files safely from the packaged dist/
  protocol.handle('app', (request) => {
    try {
      const reqUrl = new URL(request.url);
      let urlPath = reqUrl.pathname;

      // CRITICAL: If this is an API call, DO NOT handle it here.
      // It should be handled by the IPC bridge.
      if (urlPath.startsWith('/api/')) {
        logToDisk(`[PROTOCOL] Ignoring API call: ${urlPath}`);
        return new Response('Not Found', { status: 404 });
      }

      if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
      
      // Ensure path doesn't try to escape dist folder
      const normalizedPath = path.normalize(urlPath).replace(/^(\.\.[\/\\])+/, '');
      const filePath = path.join(app.getAppPath(), 'dist', normalizedPath);
      
      if (!fs.existsSync(filePath)) {
        logToDisk(`[PROTOCOL] File not found: ${filePath}`);
        return new Response('Not Found', { status: 404 });
      }
      
      const ext = path.extname(filePath).toLowerCase();
      let mimeType = 'text/plain';
      if (ext === '.js' || ext === '.mjs') mimeType = 'application/javascript';
      else if (ext === '.css') mimeType = 'text/css';
      else if (ext === '.html') mimeType = 'text/html';
      else if (ext === '.json') mimeType = 'application/json';
      else if (ext === '.png') mimeType = 'image/png';
      else if (ext === '.jpg' || ext === '.jpeg') mimeType = 'image/jpeg';
      else if (ext === '.svg') mimeType = 'image/svg+xml';
      else if (ext === '.ico') mimeType = 'image/x-icon';

      try {
        const fileData = fs.readFileSync(filePath);
        return new Response(fileData, {
          status: 200,
          headers: { 'Content-Type': mimeType }
        });
      } catch (readErr) {
        logToDisk(`[PROTOCOL] File read error: ${readErr.message}`);
        return new Response('Internal Error', { status: 500 });
      }
    } catch (err) {
      logToDisk(`[PROTOCOL ERROR] ${err.message}`);
      return new Response('Error', { status: 500 });
    }
  });

  mainWindow = new BrowserWindow({
    width: 1440, height: 900,
    minWidth: 1024, minHeight: 680,
    backgroundColor: '#080B12',
    icon: path.join(app.getAppPath(), 'its_icon.png'),
    webPreferences: {
      preload: path.join(app.getAppPath(), 'electron', 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    }
  });

  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    logToDisk(`[RENDERER] ${message} (${sourceId}:${line})`);
  });

  ipcMain.handle('api-request', async (event, args) => {
    const { method, url: reqUrl, data, headers: clientHeaders = {} } = args;
    const payload = data ? (typeof data === 'string' ? data : JSON.stringify(data)) : null;

    // Filter out hop-by-hop headers and ensure host is correctly handled
    const BLOCKED_HEADERS = new Set(['host', 'connection', 'transfer-encoding', 'content-length']);
    const forwardedHeaders = Object.fromEntries(
      Object.entries(clientHeaders)
        .filter(([k]) => !BLOCKED_HEADERS.has(k.toLowerCase()))
    );

    const options = {
      hostname: '127.0.0.1', port: 8088,
      path: reqUrl.startsWith('/api/') ? reqUrl : `/api${reqUrl.startsWith('/') ? reqUrl : '/' + reqUrl}`,
      method: method.toUpperCase(),
      headers: {
        'Content-Type': 'application/json',
        ...forwardedHeaders,
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      }
    };
    return httpRequest(options, payload);
  });

  if (!app.isPackaged) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadURL('app://kingin/');
  }

  // Auto-start backend in production mode AFTER showing the window
  if (app.isPackaged) {
    startPython();
    logToDisk('[MAIN] Backend start initiated in background.');
    // We don't await waitForBackend here to avoid blocking the UI
    waitForBackend().then(() => {
      logToDisk('[MAIN] Backend confirmed ready.');
    });
  }
});

app.on('window-all-closed', () => {
  if (pyProc && pyProc.exitCode === null) {
    try { pyProc.kill(); } catch (_) {}
  }
  app.quit();
});
