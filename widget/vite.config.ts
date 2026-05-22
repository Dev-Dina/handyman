import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/widget-app/',
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        entryFileNames: 'assets/widget-[hash].js',
        chunkFileNames: 'assets/widget-[hash].js',
        assetFileNames: 'assets/widget-[hash].[ext]',
      },
    },
  },
})
