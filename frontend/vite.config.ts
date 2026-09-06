import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Fallback if Azure Functions CORS misbehaves on Flex Consumption - uncomment
  // and set VITE_API_BASE_URL=/api in .env.local to route around it entirely:
  // server: { proxy: { '/api': { target: 'https://<functionAppName>.azurewebsites.net', changeOrigin: true, secure: true } } }
})
