import axios, { AxiosResponse } from 'axios';

// Base API configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging in dev mode
api.interceptors.request.use(
  (config) => {
    if (import.meta.env.DEV) {
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`, config.data);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and logging
api.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.log(`API Response: ${response.status}`, response.data);
    }
    return response;
  },
  (error) => {
    if (import.meta.env.DEV) {
      console.error('API Error:', error.response?.data || error.message);
    }
    return Promise.reject(error);
  }
);

// Types for API responses
export interface ClientResponse {
  id: number;
  full_name: string;
  id_number: string;
  birth_date: string;
  email?: string;
  phone?: string;
  retirement_date?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  full_name: string;
  id_number_raw: string;
  birth_date: string;
  email?: string;
  phone?: string;
  retirement_date?: string;
}

export interface EmploymentResponse {
  id: number;
  client_id: number;
  employer_id: number;
  is_current: boolean;
  start_date: string;
  end_date?: string;
  monthly_salary_nominal: number;
  created_at: string;
  updated_at: string;
}

export interface ScenarioResponse {
  id: number;
  client_id: number;
  name: string;
  description?: string;
  calculation_results: any;
  created_at: string;
  updated_at: string;
}

export interface CalculationRequest {
  client_id: number;
  scenario_name?: string;
  save_scenario?: boolean;
}

export interface CalculationResponse {
  client_id: number;
  scenario_name?: string;
  case_number: number;
  assumptions: any;
  cash_flow: Array<{
    year: number;
    month: number;
    gross_income: number;
    tax_amount: number;
    net_income: number;
    asset_balances: any;
  }>;
  summary: {
    total_gross: number;
    total_tax: number;
    total_net: number;
    final_balances: any;
  };
}

// Client API functions
export const clientApi = {
  // Create new client
  create: async (clientData: ClientCreate): Promise<ClientResponse> => {
    const response: AxiosResponse<ClientResponse> = await api.post('/api/v1/clients', clientData);
    return response.data;
  },

  // Get client by ID
  get: async (clientId: number): Promise<ClientResponse> => {
    const response: AxiosResponse<ClientResponse> = await api.get(`/api/v1/clients/${clientId}`);
    return response.data;
  },

  // Update client
  update: async (clientId: number, clientData: Partial<ClientCreate>): Promise<ClientResponse> => {
    const response: AxiosResponse<ClientResponse> = await api.patch(`/api/v1/clients/${clientId}`, clientData);
    return response.data;
  },

  // List clients with pagination
  list: async (params?: { skip?: number; limit?: number; search?: string }): Promise<ClientResponse[]> => {
    const response: AxiosResponse<ClientResponse[]> = await api.get('/api/v1/clients', { params });
    return response.data;
  },

  // Delete client
  delete: async (clientId: number): Promise<void> => {
    await api.delete(`/api/v1/clients/${clientId}`);
  },
};

// Employment API functions
export const employmentApi = {
  // Set current employer
  setCurrent: async (clientId: number, employmentData: any): Promise<EmploymentResponse> => {
    const response: AxiosResponse<EmploymentResponse> = await api.post(
      `/api/v1/clients/${clientId}/employment/set-current`,
      employmentData
    );
    return response.data;
  },

  // Plan termination
  planTermination: async (clientId: number, terminationData: any): Promise<any> => {
    const response: AxiosResponse<any> = await api.post(
      `/api/v1/clients/${clientId}/employment/plan-termination`,
      terminationData
    );
    return response.data;
  },

  // Confirm termination
  confirmTermination: async (clientId: number, terminationData: any): Promise<any> => {
    const response: AxiosResponse<any> = await api.post(
      `/api/v1/clients/${clientId}/employment/confirm-termination`,
      terminationData
    );
    return response.data;
  },

  // Get employment history
  getHistory: async (clientId: number): Promise<EmploymentResponse[]> => {
    const response: AxiosResponse<EmploymentResponse[]> = await api.get(
      `/api/v1/clients/${clientId}/employment`
    );
    return response.data;
  },
};

// Calculation API functions
export const calculationApi = {
  // Run calculation
  calculate: async (request: CalculationRequest): Promise<CalculationResponse> => {
    const response: AxiosResponse<CalculationResponse> = await api.post(
      `/api/v1/calc/${request.client_id}`,
      request
    );
    return response.data;
  },
};

// Scenario API functions
export const scenarioApi = {
  // Create scenario
  create: async (clientId: number, scenarioData: any): Promise<ScenarioResponse> => {
    const response: AxiosResponse<ScenarioResponse> = await api.post(
      `/api/v1/clients/${clientId}/scenarios`,
      scenarioData
    );
    return response.data;
  },

  // List scenarios for client
  list: async (clientId: number): Promise<ScenarioResponse[]> => {
    const response: AxiosResponse<ScenarioResponse[]> = await api.get(
      `/api/v1/clients/${clientId}/scenarios`
    );
    return response.data;
  },

  // Get scenario by ID
  get: async (clientId: number, scenarioId: number): Promise<ScenarioResponse> => {
    const response: AxiosResponse<ScenarioResponse> = await api.get(
      `/api/v1/clients/${clientId}/scenarios/${scenarioId}`
    );
    return response.data;
  },
};

// Rights fixation API functions (for document generation)
export const fixationApi = {
  // Generate 161d form
  generate161d: async (clientId: number): Promise<any> => {
    const response: AxiosResponse<any> = await api.post(`/api/v1/fixation/${clientId}/161d`);
    return response.data;
  },

  // Generate grants appendix
  generateGrantsAppendix: async (clientId: number): Promise<any> => {
    const response: AxiosResponse<any> = await api.post(`/api/v1/fixation/${clientId}/grants-appendix`);
    return response.data;
  },

  // Generate commutations appendix
  generateCommutationsAppendix: async (clientId: number): Promise<any> => {
    const response: AxiosResponse<any> = await api.post(`/api/v1/fixation/${clientId}/commutations-appendix`);
    return response.data;
  },

  // Generate complete package
  generatePackage: async (clientId: number): Promise<any> => {
    const response: AxiosResponse<any> = await api.post(`/api/v1/fixation/${clientId}/package`);
    return response.data;
  },
};

// Error handling utility
export const handleApiError = (error: any): string => {
  if (error.response?.data?.detail) {
    if (typeof error.response.data.detail === 'string') {
      return error.response.data.detail;
    }
    if (typeof error.response.data.detail === 'object') {
      // Handle validation errors
      const errors = Object.values(error.response.data.detail).flat();
      return errors.join(', ');
    }
  }
  
  if (error.response?.status === 404) {
    return 'הנתון המבוקש לא נמצא';
  }
  
  if (error.response?.status === 409) {
    return 'קיים כפילות במערכת';
  }
  
  if (error.response?.status >= 500) {
    return 'שגיאה בשרת. אנא נסה שוב מאוחר יותר';
  }
  
  return error.message || 'שגיאה לא צפויה';
};

export default api;
