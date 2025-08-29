import axios from 'axios';

// API base configuration
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '' // Production'da aynı domain
  : 'http://localhost:8002'; // Development'ta ayrı port

// Axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Request interceptor - JWT token ekleme
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired - redirect to login
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const authAPI = {
  login: (credentials) => api.post('/api/auth/login', credentials),
  logout: () => api.post('/api/auth/logout'),
  getCurrentUser: () => api.get('/api/auth/me'),
  refreshToken: () => api.post('/api/auth/refresh'),
};

export const dashboardAPI = {
  getStats: () => api.get('/api/dashboard/stats'),
  getSystemStatus: () => api.get('/api/system/status'),
  getRecentActivities: (limit = 10) => api.get(`/api/activities/recent?limit=${limit}`),
};

export const picklistAPI = {
  getOrders: (limit = 50) => api.get(`/api/picklist/orders?limit=${limit}`),
  generatePDF: (orderIds) => api.post('/api/picklist/generate', { order_ids: orderIds }),
};

export const scannerAPI = {
  getOrderLines: (orderId) => api.get(`/api/scanner/orders/${orderId}/lines`),
  scanBarcode: (orderId, barcode) => api.post('/api/scanner/scan', { order_id: orderId, barcode }),
  completeOrder: (orderId) => api.post(`/api/scanner/complete/${orderId}`),
};

export const backorderAPI = {
  getPending: () => api.get('/api/backorders/pending'),
  markCompleted: (backorderId) => api.post(`/api/backorders/${backorderId}/complete`),
};

// Helper functions
export const handleApiError = (error) => {
  console.error('API Error:', error);
  
  if (error.response) {
    // Server responded with error status
    const message = error.response.data?.detail || 
                   error.response.data?.message || 
                   `Server error: ${error.response.status}`;
    return { success: false, message, status: error.response.status };
  } else if (error.request) {
    // Network error
    return { success: false, message: 'Network error - server unreachable', status: 0 };
  } else {
    // Other error
    return { success: false, message: error.message || 'Unknown error', status: -1 };
  }
};

export const isAuthenticated = () => {
  const token = localStorage.getItem('token');
  const user = localStorage.getItem('user');
  return !!(token && user);
};

export const getCurrentUser = () => {
  try {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  } catch {
    return null;
  }
};

export const clearAuth = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
};

export default api;