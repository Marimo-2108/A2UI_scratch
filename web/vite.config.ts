import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Listen on all interfaces so the dev server is reachable through dev container port forwarding.
  server: { host: true },
})
