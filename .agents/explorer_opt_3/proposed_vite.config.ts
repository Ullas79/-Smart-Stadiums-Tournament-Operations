import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": "http://localhost:8000",
      "/state": "http://localhost:8000",
      "/role": "http://localhost:8000",
      "/simulator/scenario": "http://localhost:8000",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            // Group React core vendor files
            if (
              id.includes("react/") ||
              id.includes("react-dom/") ||
              id.includes("scheduler/")
            ) {
              return "vendor-react";
            }
            // Group Lucide icons (if any are introduced)
            if (id.includes("lucide-react")) {
              return "vendor-lucide";
            }
            // Group heavy charting packages like Recharts or D3
            if (
              id.includes("recharts") ||
              id.includes("d3")
            ) {
              return "vendor-charts";
            }
            // Fallback for all other third-party vendor dependencies
            return "vendor";
          }
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
