<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { registerUser } from '../api/users'
import AppSidebar from '../components/AppSidebar.vue'
import { BRANCH_NAMES, BRANCH_VALUES, type AuthUser, type BranchCode } from '../types/auth'

const router = useRouter()
const username = ref('')
const displayName = ref('')
const branchCode = ref<BranchCode | ''>('')
const password = ref('')
const passwordConfirmation = ref('')
const loading = ref(false)
const errorMessage = ref('')
const createdUser = ref<AuthUser | null>(null)
const canSubmit = computed(() =>
  username.value.trim().length >= 3
  && displayName.value.trim() !== ''
  && branchCode.value !== ''
  && password.value.length >= 6
  && passwordConfirmation.value.length >= 6
  && !loading.value,
)

async function submit(): Promise<void> {
  if (!canSubmit.value) return
  if (password.value !== passwordConfirmation.value) {
    errorMessage.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  errorMessage.value = ''
  createdUser.value = null
  try {
    const result = await registerUser({
      username: username.value,
      display_name: displayName.value,
      branch_code: branchCode.value as BranchCode,
      password: password.value,
      password_confirmation: passwordConfirmation.value,
    })
    createdUser.value = result.user
    username.value = ''
    displayName.value = ''
    branchCode.value = ''
    password.value = ''
    passwordConfirmation.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="workspace-shell">
    <AppSidebar />
    <div class="workspace-main">
      <header class="topbar">
        <div><p>人员注册</p><span>为工作人员创建独立账号并绑定所属分局</span></div>
        <button
          class="back-button"
          type="button"
          @click="router.push('/')"
        >
          返回工作台
        </button>
      </header>
      <main class="register-page">
        <section class="register-intro">
          <p class="eyebrow">
            ACCOUNT REGISTRATION
          </p>
          <h1>人员注册</h1>
          <p>新账号固定为业务操作员，每人使用自己的账号登录扫码终端。</p>
        </section>
        <section class="register-card">
          <form @submit.prevent="submit">
            <div class="register-grid">
              <label>登录账号<input
                v-model="username"
                name="username"
                autocomplete="off"
                placeholder="字母、数字、点、下划线或连字符"
              ></label>
              <label>人员姓名<input
                v-model="displayName"
                name="display_name"
                autocomplete="off"
                placeholder="请输入真实姓名"
              ></label>
              <label class="full-field">所属分局<select
                v-model="branchCode"
                name="branch_code"
              ><option
                value=""
                disabled
              >请选择所属分局</option><option
                v-for="code in BRANCH_VALUES"
                :key="code"
                :value="code"
              >{{ BRANCH_NAMES[code] }}</option></select></label>
              <label>初始密码<input
                v-model="password"
                name="password"
                type="password"
                autocomplete="new-password"
                placeholder="至少 6 个字符"
              ></label>
              <label>确认密码<input
                v-model="passwordConfirmation"
                name="password_confirmation"
                type="password"
                autocomplete="new-password"
                placeholder="请再次输入密码"
              ></label>
            </div>
            <p
              v-if="errorMessage"
              class="form-error"
              role="alert"
            >
              {{ errorMessage }}
            </p>
            <div
              v-if="createdUser"
              class="success-message"
              role="status"
            >
              注册成功：{{ createdUser.display_name }}（{{ createdUser.username }}）· {{ createdUser.branch_name }}
            </div>
            <div class="form-actions">
              <p>密码只用于创建账号，不会在页面或日志中留存。</p>
              <button
                type="submit"
                :disabled="!canSubmit"
              >
                {{ loading ? '正在注册…' : '注册人员' }}
              </button>
            </div>
          </form>
        </section>
      </main>
    </div>
  </div>
</template>
