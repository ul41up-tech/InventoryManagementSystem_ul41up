import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 開發時把 /api 轉發到 Flask，避免 CORS 與 cookie 問題
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
