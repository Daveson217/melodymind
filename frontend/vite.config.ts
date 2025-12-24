import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'


// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,      // Force port 5173
    strictPort: true, // Fail if port is busy instead of switching
    host: true        // Listen on all addresses (including 127.0.0.1)
  }
})