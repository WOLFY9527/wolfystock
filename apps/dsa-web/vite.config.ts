import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

function getManualChunk(id: string) {
  const normalizedId = id.replace(/\\/g, '/')
  if (!normalizedId.includes('/node_modules/')) {
    return undefined
  }
  if (
    normalizedId.includes('/node_modules/react/') ||
    normalizedId.includes('/node_modules/react-dom/') ||
    normalizedId.includes('/node_modules/scheduler/')
  ) {
    return 'vendor-react'
  }
  if (
    normalizedId.includes('/node_modules/echarts/') ||
    normalizedId.includes('/node_modules/zrender/')
  ) {
    return 'vendor-echarts'
  }
  if (normalizedId.includes('/node_modules/react-router')) {
    return 'vendor-router'
  }
  return undefined
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  server: {
    host: '0.0.0.0',  // 允许公网访问
    port: 5173,       // 默认端口
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 打包输出到项目根目录的 static 文件夹
    outDir: path.resolve(__dirname, '../../static'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: getManualChunk,
      },
    },
  },
})
