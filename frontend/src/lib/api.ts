import type {
  AgentResponse,
  AnalyticsOverview,
  Deviation,
  EvaluationMetrics,
  EventReplay,
  EvidenceStack,
  Facility,
  AdminFeatureCollection,
  FacilityContext,
  FirmsRefreshFailure,
  FirmsRefreshSummary,
  GeoFeatureCollection,
  Health,
  HistoricalIncident,
  IncidentContext,
  IncidentSummary,
  LiveSummary,
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
  health: () => request<Health>("/health"),

  listObservations: (source?: string) => request<ThermalObservation[]>(`/observations${source ? `?source=${source}` : ""}`),

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
  analyticsDataQuality: () =>
    request<{
      ingestion_batches: { batch_id: string; source: string; ingested_at: string; rows_received: number; rows_accepted: number; rows_flagged: number; rows_rejected: number; issues: Record<string, number> }[];
      coordinate_validation: {
        region_bbox: { west: number; south: number; east: number; north: number; label: string };
        total_observations: number; in_region_count: number; outside_region_count: number;
        latitude_range: [number, number] | null; longitude_range: [number, number] | null;
        outside_region_samples: { observation_id: string; latitude: number; longitude: number; source: string; timestamp: string }[];
      };
    }>(`/analytics/data-quality`),

  activeAlerts: () => request<{ event_id: string; state: string; severity: string | null; risk_score: number | null }[]>(`/alerts`),
  alertHistory: (id: string) => request<{ from_state: string | null; to_state: string; actor: string; note: string | null; changed_at: string }[]>(`/alerts/${id}/history`),

  mapEvents: () => request<GeoFeatureCollection>(`/map/events`),
  mapFacilities: () => request<GeoFeatureCollection>(`/map/facilities`),

  generateEventReport: (id: string) => request<Record<string, unknown>>(`/reports/event/${id}`, { method: "POST" }),
  eventsCsvUrl: () => `${API_BASE}/reports/events.csv`,
  eventsGeojsonUrl: () => `${API_BASE}/reports/events.geojson`,

  // Reference data -- HISTORICAL / GEOGRAPHIC, never live FIRMS.
  listIncidents: (params?: Record<string, string>) =>
    request<HistoricalIncident[]>(`/reference/incidents${params ? "?" + new URLSearchParams(params).toString() : ""}`),
  incidentSummary: () => request<IncidentSummary>(`/reference/incidents/summary`),
  getIncident: (id: string) => request<HistoricalIncident>(`/reference/incidents/${id}`),
  getIncidentContext: (id: string, radiusKm = 50) => request<IncidentContext>(`/reference/incidents/${id}/context?radius_km=${radiusKm}`),
  incidentsNear: (lat: number, lon: number, radiusKm = 50) =>
    request<{ distance_km: number; incident: HistoricalIncident }[]>(`/reference/incidents/near?lat=${lat}&lon=${lon}&radius_km=${radiusKm}`),
  adminRegions: (level: "state" | "district" = "state") => request<AdminFeatureCollection>(`/reference/admin-regions?level=${level}`),
  generateIncidentReport: (id: string) => request<Record<string, unknown>>(`/reports/historical-incident/${id}`, { method: "POST" }),

  /** Server-side NASA FIRMS refresh (the MAP_KEY never leaves the backend). Resolves with a summary or a short failure. */
  refreshFirms: async (): Promise<{ ok: true; body: FirmsRefreshSummary } | { ok: false; body: FirmsRefreshFailure | null }> => {
    try {
      const res = await fetch(`${API_BASE}/firms/refresh`, { method: "POST", cache: "no-store" });
      const body = await res.json().catch(() => null);
      return res.ok ? { ok: true, body } : { ok: false, body };
    } catch {
      return { ok: false, body: null };
    }
  },

  getFacilityContext: (eventId: string) => request<FacilityContext>(`/context/events/${eventId}`),
  liveSummary: () => request<LiveSummary>(`/context/live-summary`),

  agentQuery: (message: string) => request<AgentResponse>(`/agent/query`, { method: "POST", body: JSON.stringify({ message }) }),

  rebuildPipeline: (mode: string = "demo") => request<Record<string, unknown>>(`/pipeline/rebuild`, { method: "POST", body: JSON.stringify({ mode }) }),
};

export { ApiError, API_BASE };
