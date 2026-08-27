import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as authApi from '../api/auth'
import { ApiRequestError } from '../api/http'
import type { AuthUser } from '../types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const initialized = ref(false)

  async function login(username: string, password: string): Promise<void> {
    const result = await authApi.login(username, password)
    user.value = result.user
    initialized.value = true
  }

  async function loadCurrentUser(): Promise<void> {
    try {
      user.value = (await authApi.getCurrentUser()).user
    } catch (error) {
      if (!(error instanceof ApiRequestError) || error.code !== 'AUTH_REQUIRED') throw error
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function ensureInitialized(): Promise<void> {
    if (!initialized.value) await loadCurrentUser()
  }

  async function logout(): Promise<void> {
    await authApi.logout()
    user.value = null
    initialized.value = true
  }

  return { user, initialized, login, loadCurrentUser, ensureInitialized, logout }
})
