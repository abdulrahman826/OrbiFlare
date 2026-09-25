"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function IncidentReportButton({ incidentId }: { incidentId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const report = await api.generateIncidentReport(incidentId);
      const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `orbiflare_historical_incident_${incidentId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button onClick={download} disabled={busy} className="btn-secondary">
        {busy ? "Generating…" : "Download historical report (JSON) ↓"}
      </button>
      {error && <p className="mt-1 text-xs text-sev-critical">{error}</p>}
    </div>
  );
}
