import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // כל מה שמתחיל ב-/api יעבור ל-8005
      "/api": {
        target: "http://127.0.0.1:8005",
        changeOrigin: true,
        // אם ה-API שלכם כבר מתחיל ב-/api/v1 אין צורך ב-rewrite
        // rewrite: (path) => path,
      },
    },
  },
});
