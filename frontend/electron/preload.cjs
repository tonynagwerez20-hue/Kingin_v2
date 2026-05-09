const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  call: (args) => ipcRenderer.invoke('api-request', args),
});
