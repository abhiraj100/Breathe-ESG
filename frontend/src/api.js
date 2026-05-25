import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE,
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

export const auth = {
  login: (u, p) => api.post('/auth/login/', { username: u, password: p }),
  logout: () => api.post('/auth/logout/'),
  me: () => api.get('/auth/me/'),
};

export const dashboard = {
  stats: () => api.get('/dashboard/'),
};

export const ingest = {
  sap: (file) => { const f = new FormData(); f.append('file', file); return api.post('/ingest/sap/', f); },
  utility: (file) => { const f = new FormData(); f.append('file', file); return api.post('/ingest/utility/', f); },
  travel: (file) => { const f = new FormData(); f.append('file', file); return api.post('/ingest/travel/', f); },
};

export const records = {
  list: (params) => api.get('/records/', { params }),
  approve: (id, notes) => api.post(`/records/${id}/approve/`, { notes }),
  reject: (id, notes) => api.post(`/records/${id}/reject/`, { notes }),
  flag: (id, reason) => api.post(`/records/${id}/flag/`, { reason }),
  audit: (id) => api.get(`/records/${id}/audit/`),
  bulkApprove: (ids) => api.post('/bulk-approve/', { ids }),
};

export const batches = {
  list: () => api.get('/batches/'),
  errors: (id) => api.get(`/batches/${id}/errors/`),
};

export default api;
