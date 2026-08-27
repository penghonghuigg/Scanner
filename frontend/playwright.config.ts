import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '../tests/e2e',
  timeout: 15_000,
  use: {
    baseURL: 'http://localhost:8080',
    channel: 'msedge',
    trace: 'retain-on-failure',
  },
  reporter: 'list',
})
