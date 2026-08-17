import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Allow Cloudflare Tunnel quick-tunnel hostnames (they change on every
    // restart, so this allows any *.trycloudflare.com subdomain rather than
    // hardcoding one). Safe for local dev; Vite's dev server still only
    // binds to your machine unless a tunnel is actively forwarding to it.
    allowedHosts: ['.trycloudflare.com'],
  },
})
