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

const LOG_PATH = 'C:\\kingin_debug.log';
function logToDisk(msg) {
    const timestamp = new Date().toISOString();
    const line = `[${timestamp}] ${msg}\n`;
    try { fs.appendFileSync(LOG_PATH, line); } catch (e) {
        try { fs.appendFileSync(path.join(app.getPath('userData'), 'kingin_debug.log'), line); } catch (e2) {}
    }
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
    const spawnOpts = { 
        stdio: 'pipe', 
        cwd: path.dirname(script) 
    };

    const trySpawn = (cmd) => {
        logToDisk(`Attempting spawn: ${cmd} ${script}`);
        const proc = spawn(cmd, spawnArgs, spawnOpts);
        proc.stdout.on('data', (data) => logToDisk(`[PYTHON STDOUT] ${data.toString().trim()}`));
        proc.stderr.on('data', (data) => logToDisk(`[PYTHON STDERR] ${data.toString().trim()}`));
        proc.on('error', (err) => {
            logToDisk(`[SPAWN ERROR] ${cmd} failed: ${err.message}`);
            if (cmd === 'python') trySpawn('python3');
            else if (cmd === 'python3') trySpawn('py');
        });
        proc.on('exit', (code) => logToDisk(`[PYTHON EXIT] Code: ${code}`));
        return proc;
    };
    pyProc = trySpawn('python');
}

/**
 * Polls port 8088 until the backend responds, then resolves.
 * Times out after `maxWaitMs` milliseconds.
 */
function waitForBackend(maxWaitMs = 300000, intervalMs = 2000) {
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
                    resolve(); // proceed anyway so the UI can show an error
                }
            });
            req.end();
        };
        check();
    });
}

/**
 * Make a single HTTP request to the Python backend.
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
    // Only auto-start backend in packaged (production) mode.
    // In dev mode, `npm run dev:api` manages the backend separately.
    if (app.isPackaged) {
        startPython();
        logToDisk('[MAIN] Waiting for backend to become ready...');
        await waitForBackend();
        logToDisk('[MAIN] Backend is ready.');
    }

    ipcMain.handle('api-request', async (event, args) => {
        const { method, url, data } = args;
        const payload = data ? (typeof data === 'string' ? data : JSON.stringify(data)) : null;
        const options = {
            hostname: '127.0.0.1', port: 8088,
            // Avoid double-prefixing: /api/login must NOT become /api/api/login
            path: url.startsWith('/api/') ? url : `/api${url.startsWith('/') ? url : '/' + url}`,
            method: method.toUpperCase(),
            headers: {
                'Content-Type': 'application/json',
                'X-Control-Token': 'replit-local-control',
                ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {})
            }
        };
        return httpRequest(options, payload);
    });

    // Handle app:// protocol to serve Vite files safely
    protocol.handle('app', (request) => {
        const reqUrl = new URL(request.url);
        let urlPath = reqUrl.pathname;
        if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
        const filePath = path.join(__dirname, '..', 'dist', urlPath);
        return net.fetch(url.pathToFileURL(filePath).href);
    });

    mainWindow = new BrowserWindow({
        width: 1280, height: 800,
        backgroundColor: "#080B12",
        icon: path.join(__dirname, '..', 'its_icon.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        }
    });

    if (!app.isPackaged) { mainWindow.loadURL('http://localhost:5173'); }
    else { mainWindow.loadURL('app://kingin/'); }
});

app.on('window-all-closed', () => { if (pyProc) pyProc.kill(); app.quit(); });

