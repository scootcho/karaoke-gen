import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Allow connections from karaoke-gen frontend running on different port
    cors: true,
  },
  build: {
    minify: false,
    sourcemap: true,
  }
})
