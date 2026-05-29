import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [inspectAttr(), react()],
  resolve: {
    alias: [
      { find: "@/components/ui", replacement: path.resolve(__dirname, ".") },
      { find: "@/sections", replacement: path.resolve(__dirname, ".") },
      { find: "@/hooks", replacement: path.resolve(__dirname, ".") },
      { find: "@/lib", replacement: path.resolve(__dirname, ".") },
      { find: "@/types", replacement: path.resolve(__dirname, "./index.ts") },
      { find: "@", replacement: path.resolve(__dirname, ".") },
    ],
  },
});
