import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        // 本机 Windows 保留了 7997-8096 端口段，后端使用 8100
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
})
