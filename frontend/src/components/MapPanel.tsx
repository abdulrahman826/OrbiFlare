"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { Map as MLMap, Marker as MLMarker, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { AdminFeatureCollection, Facility, HistoricalIncident, IncidentKind, ThermalEvent, ThermalObservation } from "@/types/domain";

export const SEVERITY_HEX: Record<string, string> = {
  LOW: "#4d8a5f", MEDIUM: "#b8860b", HIGH: "#b4530f", CRITICAL: "#a82a24",
};
const SEVERITY_LETTER: Record<string, string> = { LOW: "L", MEDIUM: "M", HIGH: "H", CRITICAL: "C" };

/** Historical reference incidents have their OWN identity (blue diamond) so they can never be mistaken for live events. */
export const INCIDENT_HEX = "#3b4f8f";
export const INCIDENT_LETTER: Record<IncidentKind, string> = {
  REPORTED_INDUSTRIAL_INCIDENT: "R",
  PERSISTENT_THERMAL_SOURCE_REFERENCE: "P",
  AGRICULTURAL_BURNING_REFERENCE: "A",
  MEMORIAL_SITE_REFERENCE: "M",
};

const esc = (v: unknown) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));

const FIRMS_CONF: Record<string, string> = { l: "low", n: "nominal", h: "high" };

const EMPTY_FC = { type: "FeatureCollection", features: [] } as const;

// Free, key-less raster basemap (official OpenStreetMap tile server). It is a light basemap by nature -- see the
// `.orbiflare-map` CSS filter in globals.css for the dark treatment (the filter also applies to the vector admin
// layer below, so its colours are chosen pre-filter).
//
// A FACTORY, not a shared constant: MapLibre takes ownership of (and mutates) the style object it is given, so every
// Map instance needs its OWN style object.
function getMapStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        maxzoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
      admin: { type: "geojson", data: EMPTY_FC as never },
      obs: { type: "geojson", data: EMPTY_FC as never },
    },
    layers: [
      { id: "osm-layer", type: "raster", source: "osm" },
      { id: "admin-fill", type: "fill", source: "admin", layout: { visibility: "none" }, paint: { "fill-color": "#4a4d44", "fill-opacity": 0.03 } },
      { id: "admin-line", type: "line", source: "admin", layout: { visibility: "none" }, paint: { "line-color": "#4a4d44", "line-width": 0.8, "line-opacity": 0.5 } },
      // Raw observations: small, subordinate dots. FIRMS = dark slate, demo/synthetic = light warm grey.
      {
        id: "obs-circles", type: "circle", source: "obs",
        paint: {
          "circle-radius": 2.6, "circle-opacity": 0.8, "circle-stroke-width": 0.5, "circle-stroke-color": "#fbf9f3",
          "circle-color": ["case", ["get", "demo"], "#A39C88", "#1F2421"],
        },
      },
    ],
  };
}

function MapLegend({ showFirms, showDemoObs, showIncidents, showAdmin }: { showFirms: boolean; showDemoObs: boolean; showIncidents: boolean; showAdmin: boolean }) {
  return (
    <div className="pointer-events-none absolute bottom-2 left-2 z-10 rounded border border-base-700 bg-base-900/90 px-2 py-1.5 text-[10px] text-base-200">
      <div className="mb-1 font-semibold uppercase tracking-wider text-base-400">OrbiFlare event severity <span className="normal-case tracking-normal">(operational risk)</span></div>
      <div className="flex gap-2">
        {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((s) => (
          <span key={s} className="flex items-center gap-1">
            <span className="inline-flex h-3 w-3 items-center justify-center rounded-full font-mono text-[8px] font-bold text-white" style={{ background: SEVERITY_HEX[s] }}>{SEVERITY_LETTER[s]}</span>
            {s[0] + s.slice(1).toLowerCase()}
          </span>
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-[2px] border border-base-850 bg-base-100" />Facility</span>
        {showFirms && <span className="flex items-center gap-1"><span className="inline-block h-1.5 w-1.5 rounded-full bg-base-100" />FIRMS detection (confidence shown on click)</span>}
        {showDemoObs && <span className="flex items-center gap-1"><span className="inline-block h-1.5 w-1.5 rounded-full bg-base-500" />Demo observation</span>}
        {showIncidents && (
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rotate-45 border border-base-850" style={{ background: INCIDENT_HEX }} />Historical incident (not live)
          </span>
        )}
        {showAdmin && <span className="flex items-center gap-1"><span className="inline-block h-0 w-3 border-t border-base-300" />Admin boundary</span>}
      </div>
      <div className="mt-1 max-w-[330px] border-t border-base-700 pt-1 leading-snug text-base-400">Severity is OrbiFlare's event risk, not FIRMS detection confidence. A FIRMS detection is a thermal observation, not a confirmed fire.</div>
    </div>
  );
}

export function MapPanel({
  events = [], facilities = [], observations = [], incidents = [], adminGeoJson = null,
  height = 480, center, zoom = 4.2, autoFit = true, legend = true, highlightEventId,
}: {
  events?: ThermalEvent[]; facilities?: Facility[]; observations?: ThermalObservation[];
  incidents?: HistoricalIncident[]; adminGeoJson?: AdminFeatureCollection | null;
  height?: number; center?: [number, number]; zoom?: number; autoFit?: boolean; legend?: boolean; highlightEventId?: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<MLMarker[]>([]);
  const router = useRouter();

  // ---- map lifecycle ----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;

    // Dynamically imported (client-only, after mount): MapLibre spins up a Web Worker, and a static import in a
    // "use client" component can get that worker bundled with a mismatched path under Next's dev server.
    import("maplibre-gl").then(({ Map: MLMap, NavigationControl, setWorkerUrl }) => {
      if (cancelled || !containerRef.current) return;
      // Worker files are copied into /public by scripts/copy-maplibre-worker.mjs (see comment there).
      setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
      const map = new MLMap({
        container: containerRef.current,
        style: getMapStyle(),
        center: center || [78.5, 21.5],
        zoom,
        attributionControl: { compact: true },
      });
      map.addControl(new NavigationControl({ showCompass: false }), "top-right");
      mapRef.current = map;
      resizeObserver = new ResizeObserver(() => map.resize());
      resizeObserver.observe(containerRef.current);
      map.once("load", () => map.resize());
    });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- administrative boundary layer (real geometry from the backend) ----
  useEffect(() => {
    let raf = 0;
    const apply = () => {
      const map = mapRef.current;
      const src = map?.getSource("admin") as { setData: (d: unknown) => void } | undefined;
      if (!map || !src || !map.getLayer("admin-line")) {
        raf = requestAnimationFrame(apply);
        return;
      }
      src.setData(adminGeoJson ?? EMPTY_FC);
      const vis = adminGeoJson ? "visible" : "none";
      map.setLayoutProperty("admin-fill", "visibility", vis);
      map.setLayoutProperty("admin-line", "visibility", vis);
    };
    apply();
    return () => cancelAnimationFrame(raf);
  }, [adminGeoJson]);

  // ---- raw observations: one native GeoJSON circle layer (cheap for thousands of points) ----
  useEffect(() => {
    let raf = 0;
    const apply = () => {
      const map = mapRef.current;
      const src = map?.getSource("obs") as { setData: (d: unknown) => void } | undefined;
      if (!map || !src) {
        raf = requestAnimationFrame(apply);
        return;
      }
      src.setData({
        type: "FeatureCollection",
        features: observations.map((o) => ({
          type: "Feature", geometry: { type: "Point", coordinates: [o.longitude, o.latitude] },
          properties: { demo: o.source !== "FIRMS", sensor: o.sensor, source: o.source, frp: o.frp, ts: o.timestamp, conf: o.confidence, dn: o.day_night },
        })),
      });
    };
    apply();
    return () => cancelAnimationFrame(raf);
  }, [observations]);

  // ---- click on a raw observation -> popup (attached once the map exists) ----
  useEffect(() => {
    let raf = 0;
    let detach: (() => void) | null = null;
    const attach = () => {
      const map = mapRef.current;
      if (!map) { raf = requestAnimationFrame(attach); return; }
      const onClick = async (e: { features?: { properties?: Record<string, unknown> }[]; lngLat: { lng: number; lat: number } }) => {
        const p = e.features?.[0]?.properties;
        if (!p) return;
        const { Popup } = await import("maplibre-gl");
        const demo = p.demo === true || p.demo === "true";
        new Popup({ offset: 6 }).setLngLat(e.lngLat).setHTML(
          `<div style="font-size:11px"><b>${demo ? "Demo observation" : "FIRMS thermal observation"}</b><br/>${esc(p.sensor)} &middot; ${esc(String(p.ts).replace("T", " "))}${demo ? "" : " UTC"}<br/>FRP ${esc(p.frp ?? "--")} MW &middot; ${esc(p.dn ?? "")}<br/>FIRMS detection confidence: <b>${esc(FIRMS_CONF[String(p.conf)] ?? "n/a")}</b> (satellite attribute, not OrbiFlare severity)<br/><span style="opacity:.7">an observation, not a confirmed fire</span></div>`
        ).addTo(map);
      };
      const enter = () => { map.getCanvas().style.cursor = "pointer"; };
      const leave = () => { map.getCanvas().style.cursor = ""; };
      const bind = () => {
        if (!map.getLayer("obs-circles")) { raf = requestAnimationFrame(bind); return; }
        map.on("click", "obs-circles", onClick as never);
        map.on("mouseenter", "obs-circles", enter);
        map.on("mouseleave", "obs-circles", leave);
        detach = () => { map.off("click", "obs-circles", onClick as never); map.off("mouseenter", "obs-circles", enter); map.off("mouseleave", "obs-circles", leave); };
      };
      bind();
    };
    attach();
    return () => { cancelAnimationFrame(raf); detach?.(); };
  }, []);

  // ---- markers (DOM), drawn bottom-to-top: incidents < facilities < events (raw observations are a native layer below) ----
  useEffect(() => {
    let raf = 0;
    const tryPlace = () => {
      const map = mapRef.current;
      if (!map) {
        raf = requestAnimationFrame(tryPlace);
        return;
      }
      const place = async () => {
        const { Marker, Popup } = await import("maplibre-gl");
        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];
        const add = (el: HTMLElement, lng: number, lat: number, popupHtml: string, offset: number, href?: string) => {
          const marker = new Marker({ element: el }).setLngLat([lng, lat]).setPopup(new Popup({ offset }).setHTML(popupHtml)).addTo(map);
          if (href) {
            el.style.cursor = "pointer";
            el.setAttribute("role", "link");
            el.addEventListener("click", () => router.push(href));
          }
          markersRef.current.push(marker);
        };

        for (const i of incidents) {
          // MapLibre owns the marker element's transform (positioning), so the diamond rotation lives on a child.
          const el = document.createElement("div");
          Object.assign(el.style, { width: "18px", height: "18px", display: "flex", alignItems: "center", justifyContent: "center" });
          const diamond = document.createElement("div");
          Object.assign(diamond.style, {
            width: "13px", height: "13px", transform: "rotate(45deg)", background: INCIDENT_HEX, border: "1.5px solid #fbf9f3", boxShadow: "0 0 0 1px rgba(31,36,33,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center",
          });
          const letter = document.createElement("span");
          Object.assign(letter.style, { transform: "rotate(-45deg)", font: "700 8px ui-monospace, monospace", color: "#ffffff" });
          letter.textContent = INCIDENT_LETTER[i.record_kind];
          diamond.appendChild(letter);
          el.appendChild(diamond);
          el.setAttribute("aria-label", `Historical incident ${i.incident_id}: ${i.name}`);
          add(el, i.longitude, i.latitude,
            `<div style="font-size:12px"><b>${esc(i.name)}</b><br/>${esc(i.record_kind_label)} &middot; ${esc(i.date)}<br/>${esc(i.state)}<br/><b style="color:#3b4f8f">HISTORICAL &middot; not a FIRMS detection</b><br/><span style="opacity:.7">approximate location &middot; click for context</span></div>`,
            10, `/incidents/${i.incident_id}`);
        }

        for (const f of facilities) {
          const el = document.createElement("div");
          Object.assign(el.style, { width: "10px", height: "10px", borderRadius: "2px", background: "#1f2421", border: "1.5px solid #fbf9f3", boxShadow: "0 0 0 1px rgba(31,36,33,0.55)" });
          el.setAttribute("aria-label", `Facility ${f.name}`);
          add(el, f.longitude, f.latitude,
            `<div style="font-size:12px"><b>${esc(f.name)}</b><br/>${esc(f.facility_type)}<br/><span style="opacity:.7">facility context &middot; click to open</span></div>`,
            8, `/facilities/${f.facility_id}`);
        }

        for (const e of events) {
          const el = document.createElement("div");
          const size = 10 + Math.min(14, (e.risk_score || 0) / 8);
          const sev = e.severity || "LOW";
          Object.assign(el.style, {
            width: `${size}px`, height: `${size}px`, borderRadius: "50%", background: SEVERITY_HEX[sev],
            border: e.event_id === highlightEventId ? "2px solid #1f2421" : "1.5px solid #fbf9f3",
            boxShadow: "0 0 0 1px rgba(31,36,33,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center", font: "700 8px ui-monospace, monospace", color: "#ffffff",
          });
          el.textContent = SEVERITY_LETTER[sev];
          el.setAttribute("aria-label", `${e.event_id} ${e.severity || "unscored"} severity`);
          add(el, e.centroid_lon, e.centroid_lat,
            `<div style="font-size:12px"><b>${esc(e.event_id)}</b> ${e.is_demo ? "· DEMO" : "· LIVE"}<br/>OrbiFlare severity: <b>${esc(e.severity || "unscored")}</b> · risk ${Math.round(e.risk_score || 0)} (operational priority)<br/>FRP ${Math.round(e.peak_frp || 0)} MW · ${e.observation_count} obs<br/><span style="opacity:.7">click to investigate</span></div>`,
            10, `/investigation/${e.event_id}`);
        }
      };
      void place();
    };
    tryPlace();
    return () => cancelAnimationFrame(raf);
  }, [events, facilities, incidents, router, highlightEventId]);

  // ---- fit the viewport to what is plotted, once per distinct data set ----
  const fitKey = `${events.length}:${facilities.length}:${incidents.length}:${events[0]?.event_id ?? ""}`;
  useEffect(() => {
    if (!autoFit || center) return;
    const pts: [number, number][] = [
      ...events.map((e) => [e.centroid_lon, e.centroid_lat] as [number, number]),
      ...facilities.map((f) => [f.longitude, f.latitude] as [number, number]),
      ...incidents.map((i) => [i.longitude, i.latitude] as [number, number]),
    ];
    if (pts.length === 0) return;
    let raf = 0;
    const tryFit = () => {
      const map = mapRef.current;
      if (!map) { raf = requestAnimationFrame(tryFit); return; }
      const lons = pts.map((p) => p[0]); const lats = pts.map((p) => p[1]);
      const minX = Math.min(...lons), maxX = Math.max(...lons), minY = Math.min(...lats), maxY = Math.max(...lats);
      if (maxX - minX < 0.05 && maxY - minY < 0.05) map.jumpTo({ center: [(minX + maxX) / 2, (minY + maxY) / 2], zoom: 9 });
      else map.fitBounds([[minX, minY], [maxX, maxY]], { padding: 50, maxZoom: 10, duration: 0 });
    };
    tryFit();
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, autoFit]);

  return (
    <div className="relative" style={{ height }}>
      <div ref={containerRef} className="orbiflare-map h-full w-full rounded border border-base-700" />
      {legend && <MapLegend showFirms={observations.some((o) => o.source === "FIRMS")} showDemoObs={observations.some((o) => o.source !== "FIRMS")} showIncidents={incidents.length > 0} showAdmin={!!adminGeoJson} />}
    </div>
  );
}
