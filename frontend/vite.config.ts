import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// ⚠️ CRITICAL: DO NOT CHANGE PORTS WITHOUT COORDINATION!
// Standard ports: Frontend=3000, Backend=8005
// See START_HERE.md for details

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,              // ⚠️ DO NOT CHANGE - Frontend standard port
    host: '0.0.0.0',
    strictPort: true,
    proxy: {
      // כל מה שמתחיל ב-/api יעבור ל-8005 (השרת הראשי)
      // ⚠️ DO NOT CHANGE TARGET PORT - Backend runs on 8005
      "/api": {
        target: "http://localhost:8005",  // ⚠️ CRITICAL: Must match backend port!
        changeOrigin: true,
        secure: false,
        // אם ה-API שלכם כבר מתחיל ב-/api/v1 אין צורך ב-rewrite
        // rewrite: (path) => path,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          mui: ["@mui/material"],
          charts: ["recharts"],
          reports_vendor: ["jspdf", "jspdf-autotable", "xlsx"],
        },
      },
    },
  },
});
