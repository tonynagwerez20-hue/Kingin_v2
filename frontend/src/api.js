import axios from 'axios';

const isElectron = window.electronAPI !== undefined;

const api = axios.create({
  baseURL: isElectron ? '' : '/api',
  headers: { 'Content-Type': 'application/json' },
});

if (isElectron) {
  api.defaults.adapter = async (config) => {
    const res = await window.electronAPI.call({
      method: config.method,
      url: config.url,
      data: config.data
    });
    return {
      data: res.data,
      status: res.status,
      statusText: res.status === 200 ? 'OK' : 'Error',
      headers: {},
      config
    };
  };
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('kingin_jwt');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers['X-Control-Token'] = 'replit-local-control';
  return config;
});

export default api;
