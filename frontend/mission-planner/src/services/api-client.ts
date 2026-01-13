import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  validateStatus: (status) => status >= 200 && status < 300,
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMessage =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.response?.data?.error ||
      error.message ||
      'An unknown error occurred';

    console.error('API Error:', {
      status: error.response?.status,
      data: error.response?.data,
      message: errorMessage,
    });

    // Create a new error with a clear message
    const apiError = new Error(errorMessage);
    apiError.cause = error;
    return Promise.reject(apiError);
  }
);

export default apiClient;
