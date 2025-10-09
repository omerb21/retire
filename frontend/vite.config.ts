import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      // כל מה שמתחיל ב-/api יעבור ל-8000 (השרת הראשי)
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        // אם ה-API שלכם כבר מתחיל ב-/api/v1 אין צורך ב-rewrite
        // rewrite: (path) => path,
      },
    },
  },
});
