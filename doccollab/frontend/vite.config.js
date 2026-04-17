import { resolve } from "node:path";

import { defineConfig } from "vite";


export default defineConfig({
  base: "/static/doccollab/editor/",
  build: {
    outDir: resolve(__dirname, "../static/doccollab/editor"),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "src/main.js"),
        room: resolve(__dirname, "src/room.js"),
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return "[name].css";
          }
          return "assets/[name]-[hash][extname]";
        },
      },
    },
  },
});
