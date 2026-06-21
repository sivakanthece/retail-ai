import axios from 'axios';

const api = axios.create({ baseURL: '' });

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const authAPI = {
  login: (username, password) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);
    return api.post('/auth/token', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  },
  me: () => api.get('/auth/me'),
};

export const detectionAPI = {
  upload: (file) => {
    const form = new FormData();
    form.append('file', file);
    return api.post('/detection/upload', form);
  },
  pipeline: (eventId, detections) =>
    api.post('/detection/pipeline', { event_id: eventId, detections }),
  addToLibrary: (eventId, bbox, productName, productId = null) =>
    api.post('/detection/add-to-library', { event_id: eventId, bbox, product_name: productName, product_id: productId }),
  saveProduct: (data) => api.post('/detection/save-product', data),
  identifyProduct: (eventId, bbox) => api.post('/detection/identify-product', { event_id: eventId, bbox }),
  identifyAll: (eventId, detections) => api.post('/detection/identify-all', { event_id: eventId, detections }),
  identifyBatch: (eventId, detections, batchStart, provider) =>
    api.post('/detection/identify-batch', { event_id: eventId, detections, batch_start: batchStart, provider: provider || '' }),
  history: () => api.get('/detection/history'),
};

export const libraryAPI = {
  addRef: (file, productName, productId = null) => {
    const form = new FormData();
    form.append('file', file);
    form.append('product_name', productName);
    if (productId != null) form.append('product_id', String(productId));
    return api.post('/library/references', form);
  },
  listRefs:     ()   => api.get('/library/references'),
  listProducts: ()   => api.get('/library/products'),
  deleteRef:    (id) => api.delete(`/library/references/${id}`),
  stats:        ()   => api.get('/library/stats'),
};

export const inventoryAPI = {
  list: () => api.get('/inventory/'),
  summary: () => api.get('/inventory/summary'),
  update: (id, data) => api.put(`/inventory/${id}`, data),
  createProduct: (data) => api.post('/inventory/products', data),
  alerts: (unreadOnly = false) => api.get(`/inventory/alerts?unread_only=${unreadOnly}`),
  markAlertRead: (id) => api.put(`/inventory/alerts/${id}/read`),
};

export const nlqAPI = {
  query: (q) => api.post('/nlq/query', { query: q }),
  suggestions: () => api.get('/nlq/suggestions'),
};

export const analyticsAPI = {
  dashboard: () => api.get('/analytics/dashboard'),
};

export default api;
