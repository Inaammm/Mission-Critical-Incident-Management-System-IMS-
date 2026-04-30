import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({ baseURL: API_BASE });

export interface Incident {
  id: string;
  component_id: string;
  component_type: string;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  assigned_to: string | null;
  signal_count: number;
  first_signal_at: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  mttr_seconds: number | null;
  sla_deadline: string | null;
  sla_remaining_seconds: number | null;
}

export interface RCA {
  id: string;
  work_item_id: string;
  incident_start: string;
  incident_end: string;
  root_cause_category: string;
  root_cause_description: string;
  fix_applied: string;
  prevention_steps: string;
  created_at: string;
  created_by: string | null;
}

export interface DashboardStats {
  total_open: number;
  total_investigating: number;
  total_resolved: number;
  total_closed: number;
  signals_per_second: number;
  avg_mttr_seconds: number | null;
  p0_count: number;
  p1_count: number;
  p2_count: number;
}

export interface Signal {
  _id: string;
  component_id: string;
  error_message: string;
  error_code: string;
  latency_ms: number;
  timestamp: string;
}

export const getIncidents = (activeOnly = true) =>
  api.get<Incident[]>(`/incidents?active_only=${activeOnly}`);

export const getIncident = (id: string) =>
  api.get<Incident>(`/incidents/${id}`);

export const getIncidentSignals = (id: string) =>
  api.get<Signal[]>(`/incidents/${id}/signals`);

export const getIncidentAudit = (id: string) =>
  api.get<any[]>(`/incidents/${id}/audit`);

export const transitionIncident = (id: string, newStatus: string, performedBy = 'engineer') =>
  api.post(`/incidents/${id}/transition`, { new_status: newStatus, performed_by: performedBy });

export const submitRCA = (id: string, data: any) =>
  api.post<RCA>(`/incidents/${id}/rca`, data);

export const getRCA = (id: string) =>
  api.get<RCA>(`/incidents/${id}/rca`);

export const getDashboardStats = () =>
  api.get<DashboardStats>('/dashboard/stats');

export const simulateBurst = (count = 100) =>
  api.post(`/simulate/burst?signals_count=${count}`);

export const simulateFlood = (duration = 10, rate = 1000) =>
  api.post(`/simulate/flood?duration_seconds=${duration}&signals_per_second=${rate}`);
