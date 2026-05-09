import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const controlToken = process.env.KINGIN_API_TOKEN || 'replit-local-control'

export default defineConfig({
  base: './',
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    host: '127.0.0.1',
    allowedHosts: true,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8088',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            proxyReq.removeHeader('x-control-token')
            if (req.url === '/api/engine/start' || req.url === '/api/engine/stop') {
              proxyReq.setHeader('X-Control-Token', controlToken)
            }
          })
        }
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 2000,
  },
})
