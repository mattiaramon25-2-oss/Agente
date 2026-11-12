import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Dichiarazione minima: @types/node non è tra i pacchetti ammessi.
declare const process: { env: Record<string, string | undefined> };

const portaBackend = process.env.BACKEND_PORTA ?? '8768';

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${portaBackend}`,
        changeOrigin: true,
        rewrite: (percorso) => percorso.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
