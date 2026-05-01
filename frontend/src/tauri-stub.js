// tauri-stub.js - Bridge for React components to talk to either Tauri, Electron, or Dev API
const API_BASE = '/api';

const isElectron = window && window.process && window.process.type;
const hasElectronAPI = window && window.electronAPI;

const _call = async (path, method = 'GET', body = null) => {
  const url = `${API_BASE}${path}`;
  
  if (hasElectronAPI) {
    // Use Electron IPC Bridge (works in both dev and production)
    console.log(`[tauri-stub] Electron API Call: ${method} ${url}`);
    return window.electronAPI.call(url, {
      method,
      data: body
    });
  }

  // Fallback to fetch (Vite Dev Server Proxy)
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body) options.body = JSON.stringify(body);
  
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`API ${method} ${url} failed: ${res.status}`);
  return res.json();
};

export const invoke = async (command, args) => {
  switch (command) {
    case 'init_mt5_backend': {
      try {
        return await _call('/engine/init', 'POST', args || {});
      } catch (err) {
        console.warn('[tauri-stub] init_mt5_backend failed, using fallback:', err.message);
        return { success: true };
      }
    }

    case 'auth_mt5': {
      const data = await _call('/engine/auth', 'POST', args || {});
      return JSON.stringify(data);
    }

    case 'read_engine_state': {
      const data = await _call('/engine/state', 'GET');
      return JSON.stringify(data);
    }

    case 'start_engine': {
      const data = await _call('/engine/start', 'POST', args || {});
      return JSON.stringify(data);
    }

    case 'stop_engine': {
      const data = await _call('/engine/stop', 'POST', args || {});
      return JSON.stringify(data);
    }

    default:
      console.warn(`[tauri-stub] Unknown command: ${command}`);
      return JSON.stringify({ success: false, error: `Unknown command: ${command}` });
  }
};

export const getControlToken = async () => null;
