import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }
          if (id.includes("element-plus")) {
            return "ui-vendor";
          }
          if (id.includes("vue") || id.includes("pinia") || id.includes("vue-router")) {
            return "vue-vendor";
          }
          if (id.includes("@vueuse/core") || id.includes("axios")) {
            return "app-vendor";
          }
          if (id.includes("markdown-it") || id.includes("highlight.js")) {
            return "content-vendor";
          }
          return "misc-vendor";
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
