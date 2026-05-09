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
  const token = localStorage.getItem('kingin_jwt');
  if (token) config.headers.Authorization = `Bearer ${token}`;

  // Control token is stored after login — never hard-coded in the bundle.
  const ctrl = localStorage.getItem('kingin_ctrl');
  if (ctrl) config.headers['X-Control-Token'] = ctrl;

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('kingin_jwt');
      localStorage.removeItem('kingin_ctrl');
      // Force reload to show login screen if required, 
      // but in this version we often bypass login for local ease.
      if (window.location.pathname !== '/login') {
         // window.location.reload(); 
      }
    }
    return Promise.reject(error);
  }
);

export default api;
