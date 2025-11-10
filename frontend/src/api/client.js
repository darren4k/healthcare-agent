import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API functions
export const api = {
  // Health check
  healthCheck: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },

  // Submit a clinical note
  submitNote: async (noteData) => {
    const response = await apiClient.post('/api/intake', noteData);
    return response.data;
  },

  // Get task status
  getTaskStatus: async (taskId) => {
    const response = await apiClient.get(`/api/tasks/${taskId}`);
    return response.data;
  },

  // Get all tasks (future endpoint)
  getAllTasks: async (filters = {}) => {
    const response = await apiClient.get('/api/tasks', { params: filters });
    return response.data;
  },

  // Submit feedback
  submitFeedback: async (feedbackData) => {
    const response = await apiClient.post('/api/feedback', feedbackData);
    return response.data;
  },
};

export default apiClient;
