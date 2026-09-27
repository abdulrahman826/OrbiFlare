// Spatial decluttering for the event layer: at country-scale zooms many events project to the same few pixels. Rather than drawing a wall of
// identical circles, one representative per screen-space cell is drawn (the highest-priority event), with a count of the others; zooming in
// splits the cells until every event is drawn. Pure and deterministic (ties broken by id) so the same view always shows the same events.
export interface DeclutterItem { id: string; lng: number; lat: number; rank: number; tie: number }

export const DECLUTTER_MAX_ZOOM = 8;
export const DECLUTTER_CELL_PX = 14;

export function declutter(items: DeclutterItem[], project: (lng: number, lat: number) => { x: number; y: number }, zoom: number, cellPx = DECLUTTER_CELL_PX): { id: string; more: number }[] {
  if (zoom >= DECLUTTER_MAX_ZOOM) return items.map((i) => ({ id: i.id, more: 0 }));
  const order = [...items].sort((a, b) => b.rank - a.rank || b.tie - a.tie || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const cells = new Map<string, { id: string; more: number }>();
  for (const it of order) {
    const p = project(it.lng, it.lat);
    const key = `${Math.floor(p.x / cellPx)}:${Math.floor(p.y / cellPx)}`;
    const cur = cells.get(key);
    if (cur) cur.more += 1;
    else cells.set(key, { id: it.id, more: 0 });
  }
  return [...cells.values()];
}
