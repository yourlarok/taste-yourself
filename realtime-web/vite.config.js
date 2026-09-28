import { defineConfig } from 'vite';

export default defineConfig({
  base: '/live-mirror/',
  build: { outDir: 'dist', emptyOutDir: true }
});
