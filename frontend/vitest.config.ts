import path from "node:path";
import { defineConfig } from "vitest/config";

// Component tests render to static markup (react-dom/server) in a plain node environment: no browser, no screenshots.
export default defineConfig({
  oxc: { jsx: { runtime: "automatic" } },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
