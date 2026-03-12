import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://127.0.0.1:8545',
        changeOrigin: true,
        secure: false,
      },
      '/rpc': {
        target: 'https://127.0.0.1:8545',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/rpc/, ''),
      },
      '/ws': {
        target: 'wss://127.0.0.1:8546',
        ws: true,
        secure: false,
      },
    },
  },
})
