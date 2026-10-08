import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon-192.svg", "icon-512.svg"],
      manifest: {
        name: "LanQuiz",
        short_name: "LanQuiz",
        description: "Offline LAN multiplayer quiz",
        theme_color: "#0EA5E9",
        background_color: "#f0f9ff",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icon-192.svg", sizes: "192x192", type: "image/svg+xml" },
          { src: "icon-512.svg", sizes: "512x512", type: "image/svg+xml" },
        ],
      },
      workbox: {
        navigateFallback: "index.html",
        runtimeCaching: [
          {
            urlPattern: /^.*\/assets\/.*/i,
            handler: "CacheFirst",
            options: { cacheName: "lanquiz-assets", expiration: { maxEntries: 100 } },
          },
          {
            urlPattern: /^.*\/uploads\/.*/i,
            handler: "CacheFirst",
            options: { cacheName: "lanquiz-uploads", expiration: { maxEntries: 100 } },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": `http://127.0.0.1:${process.env.BACKEND_PORT || 8000}`,
      "/socket.io": {
        target: `http://127.0.0.1:${process.env.BACKEND_PORT || 8000}`,
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
