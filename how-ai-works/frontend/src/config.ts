// API Configuration for development and production
export const API_CONFIG = {
  // Base URL for API calls
  baseUrl: import.meta.env.PROD ? '/api' : 'http://localhost:8000/api',
  
  // Health check endpoint
  healthEndpoint: import.meta.env.PROD ? '/api/health' : 'http://localhost:8000/health',
  
  // Prediction endpoint
  predictEndpoint: import.meta.env.PROD ? '/api/predict' : 'http://localhost:8000/predict',
} as const

// Helper function to get full API URL
export const getApiUrl = (endpoint: string): string => {
  if (import.meta.env.PROD) {
    return endpoint.startsWith('/api') ? endpoint : `/api${endpoint}`
  }
  return `http://localhost:8000${endpoint.startsWith('/api') ? endpoint : `/api${endpoint}`}`
}