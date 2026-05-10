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
      data: config.data,
      headers: config.headers
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
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export const setNewsToggle = (participate) => api.post('/api/config/news_toggle', { participate });

export default api;
