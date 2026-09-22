import type {
  AgentResponse,
  AnalyticsOverview,
  Deviation,
  EvaluationMetrics,
  EventReplay,
  EvidenceStack,
  Facility,
  GeoFeatureCollection,
  Investigation,
  Risk,
  RiskTrajectory,
  ThermalEvent,
  ThermalObservation,
  ThermalTwin,
} from "@/types/domain";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; mode: string; database: string }>("/health"),

  listEvents: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<ThermalEvent[]>(`/events${qs}`);
  },
  getEvent: (id: string) => request<ThermalEvent>(`/events/${id}`),
  getEventTimeline: (id: string) => request<{ event_id: string; observations: ThermalObservation[] }>(`/events/${id}/timeline`),
  getDeviation: (id: string) => request<Deviation>(`/events/${id}/deviation`),
  getEvidence: (id: string) => request<EvidenceStack>(`/events/${id}/evidence`),
  getRisk: (id: string) => request<Risk>(`/events/${id}/risk`),
  getTrajectory: (id: string) => request<RiskTrajectory>(`/events/${id}/trajectory`),
  getReplay: (id: string) => request<EventReplay>(`/events/${id}/replay`),
  getInvestigation: (id: string) => request<Investigation>(`/events/${id}/investigation`),
  transitionEvent: (id: string, to_state: string, actor: string, note?: string) =>
    request<{ event_id: string; state: string }>(`/events/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ to_state, actor, note }),
    }),

  listFacilities: (facility_type?: string) =>
    request<Facility[]>(`/facilities${facility_type ? `?facility_type=${facility_type}` : ""}`),
  getFacility: (id: string) => request<Facility>(`/facilities/${id}`),
  getFacilityTwin: (id: string) => request<ThermalTwin>(`/facilities/${id}/thermal-twin`),
  getFacilityEvents: (id: string) => request<ThermalEvent[]>(`/facilities/${id}/events`),
  listThermalTwins: () => request<ThermalTwin[]>(`/thermal-twins`),

  analyticsOverview: () => request<AnalyticsOverview>(`/analytics/overview`),
  analyticsEvents: () => request<Record<string, unknown>>(`/analytics/events`),
  analyticsRisk: () => request<{ risk_scores: { event_id: string; risk_score: number; severity: string | null }[]; trajectory_directions: Record<string, number>; model_metrics: EvaluationMetrics }>(`/analytics/risk`),

  activeAlerts: () => request<{ event_id: string; state: string; severity: string | null; risk_score: number | null }[]>(`/alerts`),
  alertHistory: (id: string) => request<{ from_state: string | null; to_state: string; actor: string; note: string | null; changed_at: string }[]>(`/alerts/${id}/history`),

  mapEvents: () => request<GeoFeatureCollection>(`/map/events`),
  mapFacilities: () => request<GeoFeatureCollection>(`/map/facilities`),

  generateEventReport: (id: string) => request<Record<string, unknown>>(`/reports/event/${id}`, { method: "POST" }),
  eventsCsvUrl: () => `${API_BASE}/reports/events.csv`,
  eventsGeojsonUrl: () => `${API_BASE}/reports/events.geojson`,

  agentQuery: (message: string) => request<AgentResponse>(`/agent/query`, { method: "POST", body: JSON.stringify({ message }) }),

  rebuildPipeline: (mode: string = "demo") => request<Record<string, unknown>>(`/pipeline/rebuild`, { method: "POST", body: JSON.stringify({ mode }) }),
};

export { ApiError, API_BASE };
