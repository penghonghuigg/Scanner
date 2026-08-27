<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const canSubmit = computed(() => username.value.trim() !== '' && password.value !== '' && !loading.value)

async function submit(): Promise<void> {
  if (!canSubmit.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    await auth.login(username.value, password.value)
    await router.replace('/')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section
      class="brand-panel"
      aria-label="系统介绍"
    >
      <div class="brand-content">
        <div
          class="brand-mark"
          aria-hidden="true"
        >
          <svg viewBox="0 0 48 48"><path d="M13 12h22v24H13z" /><path d="M18 17h12M18 23h12M18 29h8" /></svg>
        </div>
        <p class="brand-kicker">
          HUAINAN TOBACCO
        </p>
        <h1>涉案卷烟<br>智能统计系统</h1>
        <p class="brand-description">
          规范登记 · 准确统计 · 全程留痕
        </p>
      </div>
      <p class="brand-footer">
        淮南市烟草专卖局（公司）
      </p>
    </section>
    <section class="login-panel">
      <div class="login-card">
        <div class="mobile-brand">
          <span
            class="mobile-mark"
            aria-hidden="true"
          />涉案卷烟智能统计系统
        </div>
        <p class="eyebrow">
          WELCOME BACK
        </p>
        <h2>账号登录</h2>
        <p class="login-subtitle">
          请输入您的系统账号和密码
        </p>
        <form @submit.prevent="submit">
          <label for="username">账号</label>
          <div class="field-wrap">
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
            ><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0" /></svg><input
              id="username"
              v-model="username"
              name="username"
              autocomplete="username"
              placeholder="请输入账号"
              autofocus
            >
          </div>
          <label for="password">密码</label>
          <div class="field-wrap">
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
            ><path d="M7 10V8a5 5 0 0 1 10 0v2M6 10h12v10H6z" /></svg><input
              id="password"
              v-model="password"
              name="password"
              type="password"
              autocomplete="current-password"
              placeholder="请输入密码"
            >
          </div>
          <p
            v-if="errorMessage"
            class="form-error"
            role="alert"
          >
            {{ errorMessage }}
          </p>
          <button
            type="submit"
            :disabled="!canSubmit"
          >
            <span>{{ loading ? '正在登录…' : '登录系统' }}</span><svg
              v-if="!loading"
              viewBox="0 0 24 24"
              aria-hidden="true"
            ><path d="m9 18 6-6-6-6" /></svg>
          </button>
        </form>
        <p class="security-note">
          <span aria-hidden="true">●</span> 系统采用安全会话保护您的账号信息
        </p>
      </div>
    </section>
  </main>
</template>
