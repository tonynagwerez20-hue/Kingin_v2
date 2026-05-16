/**
 * KingIn Preload Script — IPC Bridge
 * Exposes a safe API from Electron to the React renderer.
 * React calls window.electronAPI.* to communicate with the backend.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Detect Electron environment
  isElectron: true,

  // Forward API requests through Electron → Python backend
  apiRequest: (args) => ipcRenderer.invoke('api-request', args),

  // Window controls (custom titlebar)
  minimize:   () => ipcRenderer.send('win-minimize'),
  maximize:   () => ipcRenderer.send('win-maximize'),
  close:      () => ipcRenderer.send('win-close'),
  hideToTray: () => ipcRenderer.send('win-hide'),

  // Trade signal notification
  notifySignal: (signal) => ipcRenderer.send('trade-signal', signal),

  // Open log file
  openLog: () => ipcRenderer.send('open-log'),
});
