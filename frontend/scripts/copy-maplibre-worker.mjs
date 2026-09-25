// MapLibre GL 6 runs geometry/GeoJSON processing in a module Web Worker. Bundler-resolved worker URLs are unreliable
// under Next.js, which silently stalls every vector/GeoJSON layer (raster tiles still work). We serve the worker files
// ourselves from /public and point MapLibre at them (see MapPanel.tsx). This runs before `dev` and `build`.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "maplibre-gl", "dist");
const dest = join(root, "public", "maplibre");
mkdirSync(dest, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  if (!existsSync(join(src, f))) throw new Error(`missing ${f} in maplibre-gl/dist -- did the package layout change?`);
  copyFileSync(join(src, f), join(dest, f));
}
console.log("maplibre worker files copied to public/maplibre");
