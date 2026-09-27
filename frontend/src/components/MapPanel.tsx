"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { Map as MLMap, Marker as MLMarker, Popup as MLPopup, StyleSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { DECLUTTER_MAX_ZOOM, declutter } from "@/lib/declutter";
import { DEFAULT_MAP_FOCUS, MAP_FOCUS_LABEL, MAP_FOCUS_ORDER, displayPriority, eventsForFocus, type MapFocus } from "@/lib/mapFocus";
import { INTERP_HEX, INTERP_LABEL, INTERP_ORDER, SEVERITY_RING, markerStyle, popupHtml, tooltipText } from "@/lib/interpretation";
import type { AdminFeatureCollection, Facility, HistoricalIncident, IncidentKind, ThermalEvent, ThermalObservation } from "@/types/domain";

/** Operational-priority ring colours (used by GIS filters and the map key). Fill colours are NEVER taken from this palette. */
export const SEVERITY_HEX: Record<string, string> = Object.fromEntries(Object.entries(SEVERITY_RING).map(([k, v]) => [k, v.color]));

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
const FAC_ICON = "fac-square";
const NEUTRAL_FILL = "#e2dfd3";

// Event radius (centre) in px by priority, growing gently with zoom. Ring width comes from the feature. Numbers: 3.75-5 px radius = 7.5-10 px centre.
const EVENT_BASE_RADIUS = ["match", ["get", "sev"], "CRITICAL", 5, "HIGH", 5, "MEDIUM", 4, 3.75];

// Free, key-less raster basemap (official OpenStreetMap tile server), desaturated INSIDE the raster layer so the event/facility colours drawn on
// the same canvas are never filtered. A FACTORY, not a shared constant: MapLibre mutates the style object it is given.
export function getMapStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
      admin: { type: "geojson", data: EMPTY_FC as never },
      obs: { type: "geojson", data: EMPTY_FC as never },
      facilities: { type: "geojson", data: EMPTY_FC as never },
      events: { type: "geojson", data: EMPTY_FC as never },
    },
    layers: [
      { id: "osm-layer", type: "raster", source: "osm", paint: { "raster-saturation": -0.78, "raster-contrast": -0.12, "raster-brightness-min": 0.06, "raster-brightness-max": 0.97, "raster-opacity": 0.85 } },
      { id: "admin-fill", type: "fill", source: "admin", layout: { visibility: "none" }, paint: { "fill-color": "#4a4d44", "fill-opacity": 0.03 } },
      { id: "admin-line", type: "line", source: "admin", layout: { visibility: "none" }, paint: { "line-color": "#4a4d44", "line-width": 0.7, "line-opacity": 0.4 } },
      // 5. Raw FIRMS observations: tiny, low-opacity dots (subordinate to everything above them). No ring, no text.
      {
        id: "obs-circles", type: "circle", source: "obs",
        paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 1, 10, 2.2], "circle-opacity": 0.4, "circle-color": ["case", ["get", "demo"], "#A39C88", "#1F2421"] },
      },
      // 5b. Uncertain LOW events: tiny, faint, neutral background dots (no ring, no colour). They fade in as the user zooms in.
      {
        id: "event-faint", type: "circle", source: "events", filter: ["==", ["get", "faint"], true],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 1.2, 7, 1.7, 10, 3],
          "circle-color": "#9d9a8e",
          "circle-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.22, 6, 0.3, 9, 0.6, 12, 0.85],
        },
      },
      // 6. Events (drawn last = on top). Fill = source interpretation, outer ring = operational priority. Higher priority is drawn above lower.
      {
        id: "event-circles", type: "circle", source: "events", filter: ["==", ["get", "faint"], false], layout: { "circle-sort-key": ["get", "rank"] },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, ["*", EVENT_BASE_RADIUS as never, 0.85], 8, ["*", EVENT_BASE_RADIUS as never, 1.1], 12, ["*", EVENT_BASE_RADIUS as never, 1.5]],
          "circle-color": ["get", "fill"], "circle-stroke-color": ["get", "ring"], "circle-stroke-width": ["get", "ringPx"], "circle-opacity": 1, "circle-stroke-opacity": 1,
        },
      },
      { id: "event-highlight", type: "circle", source: "events", filter: ["==", ["get", "id"], ""], paint: { "circle-radius": 11, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#1f2421", "circle-stroke-width": 2 } },
    ],
  };
}

/** A real marker sample for the key: the same construction as on the map (fill + outer ring). */
function MarkerSample({ fill, ring, px, size = 10 }: { fill: string; ring: string; px: number; size?: number }) {
  return <span className="inline-block shrink-0 rounded-full" style={{ width: size, height: size, background: fill, boxShadow: `0 0 0 ${px}px ${ring}`, margin: px }} aria-hidden />;
}

/** Compact map key. It sits BELOW the map (never over it), so the geography is never obscured. */
export function MapKey({ showFirms, showDemoObs, showIncidents, showAdmin, focus }: { showFirms: boolean; showDemoObs: boolean; showIncidents: boolean; showAdmin: boolean; focus?: MapFocus }) {
  const H = "mb-1 text-[9px] font-bold uppercase tracking-[0.12em] text-base-400";
  return (
    <div className="rounded border border-base-700 bg-base-850 px-2.5 py-2 text-[10px] text-base-200" data-testid="map-key">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-base-100">Map key</span>
        <span className="text-base-400">Fill = source interpretation · Ring = operational priority</span>
      </div>
      {focus && (
        <div className="mt-0.5 text-base-400" data-testid="map-key-focus">
          <b className="text-base-200">FOCUS: {MAP_FOCUS_LABEL[focus].toUpperCase()}</b> · Uncertain events remain available under All Events.
        </div>
      )}
      <div className="mt-1.5 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-3">
        <div data-testid="legend-interpretation">
          <div className={H}>Thermal source</div>
          <div className="space-y-0.5">
            {INTERP_ORDER.map((c) => (
              <div key={c} className="flex items-center gap-1.5">
                <MarkerSample fill={INTERP_HEX[c].fill} ring={SEVERITY_RING.LOW.color} px={1} />
                {c === "NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE" ? "Natural / other" : INTERP_LABEL[c]}
              </div>
            ))}
          </div>
        </div>
        <div data-testid="legend-priority">
          <div className={H}>Operational priority</div>
          <div className="space-y-0.5">
            {([["HIGH", "High / Critical"], ["MEDIUM", "Medium"], ["LOW", "Low"]] as const).map(([s, label]) => (
              <div key={s} className="flex items-center gap-1.5">
                <MarkerSample fill={NEUTRAL_FILL} ring={SEVERITY_RING[s].color} px={SEVERITY_RING[s].px} />
                {label}
              </div>
            ))}
          </div>
        </div>
        <div data-testid="legend-context">
          <div className={H}>Context</div>
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5"><span className="inline-block h-[7px] w-[7px] shrink-0 border border-base-100 bg-base-400" aria-hidden />Facility (spatial context)</div>
            {showFirms && <div className="flex items-center gap-1.5"><span className="inline-block h-[3px] w-[3px] shrink-0 rounded-full bg-base-100 opacity-50" aria-hidden />FIRMS observation</div>}
            {showDemoObs && <div className="flex items-center gap-1.5"><span className="inline-block h-[3px] w-[3px] shrink-0 rounded-full bg-base-500" aria-hidden />Demo observation</div>}
            {showIncidents && <div className="flex items-center gap-1.5"><span className="inline-block h-2 w-2 shrink-0 rotate-45 border border-base-850" style={{ background: INCIDENT_HEX }} aria-hidden />Historical incident (not live)</div>}
            {showAdmin && <div className="flex items-center gap-1.5"><span className="inline-block h-0 w-3 shrink-0 border-t border-base-300" aria-hidden />Admin boundary</div>}
          </div>
        </div>
      </div>
      <p className="mt-1.5 border-t border-base-700 pt-1 text-[9px] text-base-500">Candidate labels only: a FIRMS detection is a thermal observation, not a confirmed fire. Dense areas show the highest-priority event per spot; zoom in to see each.</p>
    </div>
  );
}
export const MapLegend = MapKey;

const LAYERS_TOP_FIRST = ["event-circles", "facility-squares", "event-faint", "obs-circles"];
const isEventLayer = (id: string) => id === "event-circles" || id === "event-faint";

function facilitySquare(): ImageData | null {
  const c = document.createElement("canvas");
  c.width = c.height = 12;
  const g = c.getContext("2d");
  if (!g) return null;
  g.fillStyle = "#fbf9f3"; g.fillRect(0, 0, 12, 12);
  g.fillStyle = "#5a5d54"; g.fillRect(1.5, 1.5, 9, 9);
  return g.getImageData(0, 0, 12, 12);
}

export function MapPanel({
  events = [], facilities = [], observations = [], incidents = [], adminGeoJson = null,
  height = 480, center, zoom = 4.2, autoFit = true, legend = true, highlightEventId, focusControl = false,
}: {
  events?: ThermalEvent[]; facilities?: Facility[]; observations?: ThermalObservation[];
  incidents?: HistoricalIncident[]; adminGeoJson?: AdminFeatureCollection | null;
  height?: number; center?: [number, number]; zoom?: number; autoFit?: boolean; legend?: boolean; highlightEventId?: string; focusControl?: boolean;
}) {
  // FOCUS is a display filter only: it never changes an event, its counts elsewhere, or any stored state. Default = actionable.
  const [focus, setFocus] = useState<MapFocus>(DEFAULT_MAP_FOCUS);
  const allEvents = events;
  const shown = useMemo(() => (focusControl ? eventsForFocus(allEvents, focus) : allEvents), [allEvents, focus, focusControl]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<MLMarker[]>([]);
  const eventsById = useRef<Map<string, ThermalEvent>>(new Map());
  const facilitiesById = useRef<Map<string, Facility>>(new Map());
  const moreById = useRef<Map<string, number>>(new Map());
  const router = useRouter();

  // ---- map lifecycle ----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    import("maplibre-gl").then(({ Map: MLMap, NavigationControl, setWorkerUrl }) => {
      if (cancelled || !containerRef.current) return;
      setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");   // copied into /public by scripts/copy-maplibre-worker.mjs
      const map = new MLMap({ container: containerRef.current, style: getMapStyle(), center: center || [78.5, 21.5], zoom, attributionControl: { compact: true } });
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

  // ---- administrative boundary layer ----
  useEffect(() => {
    let raf = 0;
    const apply = () => {
      const map = mapRef.current;
      const src = map?.getSource("admin") as { setData: (d: unknown) => void } | undefined;
      if (!map || !src || !map.getLayer("admin-line")) { raf = requestAnimationFrame(apply); return; }
      src.setData(adminGeoJson ?? EMPTY_FC);
      const vis = adminGeoJson ? "visible" : "none";
      map.setLayoutProperty("admin-fill", "visibility", vis);
      map.setLayoutProperty("admin-line", "visibility", vis);
    };
    apply();
    return () => cancelAnimationFrame(raf);
  }, [adminGeoJson]);

  // ---- raw observations (native layer, tiny subordinate dots) ----
  useEffect(() => {
    let raf = 0;
    const apply = () => {
      const map = mapRef.current;
      const src = map?.getSource("obs") as { setData: (d: unknown) => void } | undefined;
      if (!map || !src) { raf = requestAnimationFrame(apply); return; }
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

  // ---- facilities: neutral square symbols (spatial context only) ----
  useEffect(() => {
    facilitiesById.current = new Map(facilities.map((f) => [f.facility_id, f] as const));
    let raf = 0;
    const apply = () => {
      const map = mapRef.current;
      const src = map?.getSource("facilities") as { setData: (d: unknown) => void } | undefined;
      if (!map || !src) { raf = requestAnimationFrame(apply); return; }
      src.setData({ type: "FeatureCollection", features: facilities.map((f) => ({ type: "Feature", geometry: { type: "Point", coordinates: [f.longitude, f.latitude] }, properties: { id: f.facility_id } })) });
    };
    apply();
    return () => cancelAnimationFrame(raf);
  }, [facilities]);

  // ---- events: one native layer; decluttered by screen-space cell at country-scale zooms ----
  useEffect(() => {
    eventsById.current = new Map(allEvents.map((e) => [e.event_id, e] as const));
    let raf = 0;
    let bound: MLMap | null = null;
    const render = () => {
      const map = mapRef.current;
      const src = map?.getSource("events") as { setData: (d: unknown) => void } | undefined;
      if (!map || !src) return false;
      const items = shown.map((e) => ({ id: e.event_id, lng: e.centroid_lon, lat: e.centroid_lat, rank: displayPriority(e), tie: e.risk_score || 0 }));
      const reps = declutter(items, (lng, lat) => map.project([lng, lat]), map.getZoom());
      moreById.current = new Map(reps.map((r) => [r.id, r.more] as const));
      src.setData({
        type: "FeatureCollection",
        features: reps.map((r) => {
          const e = eventsById.current.get(r.id) as ThermalEvent;
          const ms = markerStyle(e);
          return {
            type: "Feature", geometry: { type: "Point", coordinates: [e.centroid_lon, e.centroid_lat] },
            properties: { id: e.event_id, sev: e.severity || "LOW", rank: ms.rank, fill: ms.fill, ring: ms.ringColor, ringPx: ms.ringPx, faint: ms.faint, more: r.more },
          };
        }),
      });
      map.setFilter("event-highlight", ["==", ["get", "id"], highlightEventId ?? ""]);
      return true;
    };
    const start = () => {
      const map = mapRef.current;
      if (!map || !render()) { raf = requestAnimationFrame(start); return; }
      map.on("moveend", render);                       // re-declutter after every zoom / pan
      bound = map;
    };
    start();
    return () => { cancelAnimationFrame(raf); bound?.off("moveend", render); };
  }, [shown, allEvents, highlightEventId]);

  // ---- interactions: hover tooltip, click popup (events > facilities > raw observations). Markers never navigate. ----
  useEffect(() => {
    let raf = 0;
    let cleanup: (() => void) | null = null;
    let cancelled = false;
    const setup = async () => {
      const map = mapRef.current;
      if (!map || !map.getLayer("event-circles")) { raf = requestAnimationFrame(setup); return; }
      const { Popup } = await import("maplibre-gl");
      if (cancelled) return;
      if (!map.hasImage(FAC_ICON)) {
        const img = facilitySquare();
        if (img) map.addImage(FAC_ICON, img);
      }
      if (!map.getLayer("facility-squares")) {
        map.addLayer({ id: "facility-squares", type: "symbol", source: "facilities", layout: { "icon-image": FAC_ICON, "icon-size": 0.62, "icon-allow-overlap": true, "icon-ignore-placement": true } }, "event-circles");
      }
      let tip: MLPopup | null = null;
      let pinned: MLPopup | null = null;
      let tipId = "";
      const hit = (pt: { x: number; y: number }) => map.queryRenderedFeatures([[pt.x - 4, pt.y - 4], [pt.x + 4, pt.y + 4]], { layers: LAYERS_TOP_FIRST.filter((l) => map.getLayer(l)) });
      const clearTip = () => { tip?.remove(); tip = null; tipId = ""; };
      const onMove = (ev: { point: { x: number; y: number } }) => {
        const f = hit(ev.point)[0];
        map.getCanvas().style.cursor = f ? "pointer" : "";
        if (!f || !isEventLayer(f.layer.id)) { clearTip(); return; }
        const id = String(f.properties?.id);
        if (id === tipId) return;
        const e = eventsById.current.get(id);
        if (!e) return;
        clearTip();
        tipId = id;
        const more = moreById.current.get(id) ?? 0;
        tip = new Popup({ closeButton: false, closeOnClick: false, offset: 9, className: "orbiflare-tip" })
          .setLngLat((f.geometry as unknown as { coordinates: [number, number] }).coordinates)
          .setHTML(`<div style="font-size:11px;line-height:1.35">${tooltipText(e).split("\n").map(esc).join("<br/>")}${more > 0 ? `<br/><span style="opacity:.65">+${more} more nearby</span>` : ""}</div>`)
          .addTo(map);
      };
      const onLeave = () => { clearTip(); map.getCanvas().style.cursor = ""; };
      const onClick = (ev: { point: { x: number; y: number } }) => {
        const f = hit(ev.point)[0];
        if (!f) return;
        clearTip();
        pinned?.remove();
        const coords = (f.geometry as unknown as { coordinates: [number, number] }).coordinates;
        let html = "";
        if (isEventLayer(f.layer.id)) {
          const id = String(f.properties?.id);
          const e = eventsById.current.get(id);
          if (!e) return;
          const fac = e.facility_id ? facilitiesById.current.get(e.facility_id) : undefined;
          const more = moreById.current.get(id) ?? 0;
          html = popupHtml(e, fac?.name) + (more > 0 ? `<div style="font-size:10px;opacity:.7;margin-top:4px">+${more} more event(s) in this area — zoom in to see each one.</div>` : "");
        } else if (f.layer.id === "facility-squares") {
          const fac = facilitiesById.current.get(String(f.properties?.id));
          if (!fac) return;
          html = `<div style="font-size:12px"><b>${esc(fac.name)}</b><br/>${esc(fac.facility_type)}<br/><span style="opacity:.7">facility context (spatial association, not source attribution)</span><br/><a href="/facilities/${esc(fac.facility_id)}" style="font-weight:700;text-decoration:underline">Open facility &rarr;</a></div>`;
        } else {
          const p = f.properties ?? {};
          const demo = p.demo === true || p.demo === "true";
          html = `<div style="font-size:11px"><b>${demo ? "Demo observation" : "FIRMS thermal observation"}</b><br/>${esc(p.sensor)} &middot; ${esc(String(p.ts).replace("T", " "))}${demo ? "" : " UTC"}<br/>FRP ${esc(p.frp ?? "--")} MW &middot; ${esc(p.dn ?? "")}<br/>FIRMS detection confidence: <b>${esc(FIRMS_CONF[String(p.conf)] ?? "n/a")}</b> (satellite attribute, not OrbiFlare priority)<br/><span style="opacity:.7">an observation, not a confirmed fire</span></div>`;
        }
        pinned = new Popup({ offset: 9, maxWidth: "300px" }).setLngLat(coords).setHTML(html).addTo(map);
      };
      map.on("mousemove", onMove);
      map.on("mouseout", onLeave);
      map.on("click", onClick);
      cleanup = () => { map.off("mousemove", onMove); map.off("mouseout", onLeave); map.off("click", onClick); clearTip(); pinned?.remove(); };
    };
    void setup();
    return () => { cancelled = true; cancelAnimationFrame(raf); cleanup?.(); };
  }, []);

  // ---- historical incidents: their own (few) DOM markers, always distinct from live events ----
  useEffect(() => {
    let raf = 0;
    const tryPlace = () => {
      const map = mapRef.current;
      if (!map) { raf = requestAnimationFrame(tryPlace); return; }
      const place = async () => {
        const { Marker, Popup } = await import("maplibre-gl");
        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];
        for (const i of incidents) {
          const el = document.createElement("div");
          Object.assign(el.style, { width: "14px", height: "14px", display: "flex", alignItems: "center", justifyContent: "center" });
          const diamond = document.createElement("div");
          Object.assign(diamond.style, { width: "11px", height: "11px", transform: "rotate(45deg)", background: INCIDENT_HEX, border: "1.5px solid #fbf9f3", boxShadow: "0 0 0 1px rgba(31,36,33,0.55)" });
          el.appendChild(diamond);
          el.setAttribute("aria-label", `Historical incident ${i.incident_id}: ${i.name}`);
          el.style.cursor = "pointer";
          el.setAttribute("role", "link");
          el.addEventListener("click", () => router.push(`/incidents/${i.incident_id}`));
          const marker = new Marker({ element: el }).setLngLat([i.longitude, i.latitude])
            .setPopup(new Popup({ offset: 10 }).setHTML(`<div style="font-size:12px"><b>${esc(i.name)}</b><br/>${esc(i.record_kind_label)} &middot; ${esc(i.date)}<br/>${esc(i.state)}<br/><b style="color:#3b4f8f">HISTORICAL &middot; not a FIRMS detection</b><br/><span style="opacity:.7">approximate location &middot; click for context</span></div>`)).addTo(map);
          markersRef.current.push(marker);
        }
      };
      void place();
    };
    tryPlace();
    return () => cancelAnimationFrame(raf);
  }, [incidents, router]);

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
    <div className="space-y-1.5">
      {focusControl && (
        <div className="flex flex-wrap items-center justify-between gap-2" role="group" aria-label="Map focus" data-testid="map-focus">
          <span className="text-[9px] font-bold uppercase tracking-[0.14em] text-base-400">Focus</span>
          <div className="flex overflow-hidden rounded border border-base-600">
            {MAP_FOCUS_ORDER.map((f) => (
              <button key={f} type="button" onClick={() => setFocus(f)} aria-pressed={focus === f} data-focus={f}
                className={`px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${focus === f ? "bg-accent text-white" : "bg-base-850 text-base-300 hover:text-base-100"}`}>
                {MAP_FOCUS_LABEL[f]} <span className="font-mono opacity-70">{eventsForFocus(allEvents, f).length}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="relative" style={{ height }}>
        <div ref={containerRef} className="orbiflare-map h-full w-full rounded border border-base-700" />
      </div>
      {legend && <MapKey focus={focusControl ? focus : undefined} showFirms={observations.some((o) => o.source === "FIRMS")} showDemoObs={observations.some((o) => o.source !== "FIRMS")} showIncidents={incidents.length > 0} showAdmin={!!adminGeoJson} />}
    </div>
  );
}

export { DECLUTTER_MAX_ZOOM };
