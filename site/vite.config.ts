import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [
    // Must be registered BEFORE the react plugin.
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
  ],
  define: {
    // Baked in at build time. The workflow deploys on EVERY monitor run, but
    // the repo is only committed to when data actually changes - so without
    // this the header would read "Data as of yesterday" on a quiet day and
    // look broken. This is what proves the monitor is still alive.
    __BUILT_AT__: JSON.stringify(new Date().toISOString()),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})
