"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { Map as MLMap, Marker as MLMarker, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Facility, ThermalEvent } from "@/types/domain";

const SEVERITY_HEX: Record<string, string> = {
  LOW: "#4a9a6a", MEDIUM: "#c9a227", HIGH: "#d97b3f", CRITICAL: "#d1453f",
};

// Free, key-less raster basemap (official OpenStreetMap tile server) so the
// map works with zero paid API configuration and no vector-tile worker
// dependency. It's a light basemap by nature -- see the `.orbiflare-map`
// CSS filter in globals.css for the dark-theme treatment. Swap this for a
// vector provider style if richer basemap detail is desired in a
// deployment with a key configured.
const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm-layer", type: "raster", source: "osm" }],
};

export function MapPanel({
  events = [], facilities = [], height = 480, center, zoom = 4.2,
}: {
  events?: ThermalEvent[]; facilities?: Facility[]; height?: number; center?: [number, number]; zoom?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<MLMarker[]>([]);
  const router = useRouter();

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;

    // Dynamically imported (client-only, after mount) rather than statically
    // imported at module scope -- MapLibre GL JS spins up a Web Worker via
    // `new Worker(new URL(...), { type: "module" })`, and importing it as a
    // static top-level dependency of a "use client" component can get that
    // worker bundled/served with a mismatched path under Next's dev server,
    // which silently stalls style loading. A dynamic import avoids that.
    import("maplibre-gl").then(({ Map: MLMap, NavigationControl }) => {
      if (cancelled || !containerRef.current) return;
      const map = new MLMap({
        container: containerRef.current,
        style: MAP_STYLE,
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

        for (const f of facilities) {
          const el = document.createElement("div");
          el.style.width = "10px";
          el.style.height = "10px";
          el.style.borderRadius = "2px";
          el.style.background = "#5a6169";
          el.style.border = "1px solid #a8adb3";
          el.style.cursor = "pointer";
          const marker = new Marker({ element: el })
            .setLngLat([f.longitude, f.latitude])
            .setPopup(new Popup({ offset: 8 }).setHTML(`<div style="font-size:12px"><b>${f.name}</b><br/>${f.facility_type}</div>`))
            .addTo(map);
          el.addEventListener("click", () => router.push(`/facilities/${f.facility_id}`));
          markersRef.current.push(marker);
        }

        for (const e of events) {
          const el = document.createElement("div");
          const size = 10 + Math.min(14, (e.risk_score || 0) / 8);
          el.style.width = `${size}px`;
          el.style.height = `${size}px`;
          el.style.borderRadius = "50%";
          el.style.background = SEVERITY_HEX[e.severity || "LOW"];
          el.style.border = "2px solid rgba(255,255,255,0.25)";
          el.style.cursor = "pointer";
          el.style.boxShadow = "0 0 6px rgba(0,0,0,0.6)";
          const marker = new Marker({ element: el })
            .setLngLat([e.centroid_lon, e.centroid_lat])
            .setPopup(
              new Popup({ offset: 10 }).setHTML(
                `<div style="font-size:12px"><b>${e.event_id}</b><br/>${e.severity || "unscored"} · risk ${Math.round(e.risk_score || 0)}<br/>FRP ${Math.round(e.peak_frp || 0)} MW</div>`
              )
            )
            .addTo(map);
          el.addEventListener("click", () => router.push(`/investigation/${e.event_id}`));
          markersRef.current.push(marker);
        }
      };

      if (map.isStyleLoaded()) place();
      else map.once("load", place);
    };
    tryPlace();
    return () => cancelAnimationFrame(raf);
  }, [events, facilities, router]);

  return <div ref={containerRef} style={{ height }} className="orbiflare-map w-full rounded-md border border-base-700" />;
}
