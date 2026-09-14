import api from './api';

export interface DashboardStats {
  total_faculty: number;
  total_publications: number;
  verified_publications: number;
  pending_review: number;
  flagged_records: number;
  total_citations: number;
  h_index?: number;
  i10_index?: number;
}

export interface AgentStatus {
  name: string;
  status: string;
  phase: number;
}

export const dashboardService = {
  getStats: async (faculty_id?: string): Promise<DashboardStats> => {
    const url = faculty_id ? `/api/v1/analytics/dashboard?faculty_id=${faculty_id}` : '/api/v1/analytics/dashboard';
    const res = await api.get(url);
    return res.data;
  },

  getAgentStatus: async (): Promise<{ agents: AgentStatus[] }> => {
    const res = await api.get('/api/v1/agents/status');
    return res.data;
  }
};
