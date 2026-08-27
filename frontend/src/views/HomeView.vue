<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loggingOut = ref(false)
const roleNames = { ADMIN: '系统管理员', OPERATOR: '业务操作员', VIEWER: '只读用户' }
const roleName = computed(() => auth.user ? roleNames[auth.user.role] : '')
const canManageUsers = computed(() => auth.user?.role === 'ADMIN')
const canCreateSession = computed(() => auth.user?.role !== 'VIEWER')
const branchLabel = computed(() => auth.user?.branch_name ?? '系统管理')

async function logout(): Promise<void> {
  loggingOut.value = true
  try { await auth.logout(); await router.replace('/login') } finally { loggingOut.value = false }
}
</script>

<template>
  <div class="workspace-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="sidebar-logo">案</span><span>涉案卷烟<br><small>智能统计系统</small></span>
      </div>
      <nav aria-label="主导航">
        <RouterLink
          class="nav-item active"
          to="/"
        >
          <span>⌂</span>系统首页
        </RouterLink>
        <RouterLink
          class="nav-item"
          to="/scan-sessions"
        >
          <span>▤</span>扫描批次
        </RouterLink>
        <RouterLink
          v-if="canManageUsers"
          class="nav-item"
          to="/users/register"
        >
          <span>＋</span>人员注册
        </RouterLink>
        <RouterLink
          v-if="canManageUsers"
          class="nav-item"
          to="/products"
        >
          <span>▦</span>品规管理
        </RouterLink>
      </nav>
      <div class="sidebar-version">
        内部业务系统<br>Version 0.1.0
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div><p>工作台</p><span>欢迎使用涉案卷烟智能统计系统</span></div>
        <div class="user-menu">
          <span class="avatar">{{ auth.user?.display_name.slice(0, 1) }}</span><span><strong>{{ auth.user?.display_name }}</strong><small>{{ roleName }}</small></span><button
            type="button"
            :disabled="loggingOut"
            @click="logout"
          >
            {{ loggingOut ? '退出中…' : '退出登录' }}
          </button>
        </div>
      </header>
      <main class="dashboard">
        <section class="welcome-card">
          <div>
            <p class="eyebrow">
              SYSTEM OVERVIEW
            </p><h1>{{ auth.user?.display_name }}，您好</h1><p>登录状态正常，系统已准备就绪。</p>
          </div><div class="status-badge">
            <span />运行正常
          </div>
        </section>
        <section class="quick-actions">
          <RouterLink
            v-if="canCreateSession"
            data-action="new-session"
            class="quick-primary"
            to="/scan-sessions/new"
          >
            <span>＋</span><div><strong>新建扫描批次</strong><small>登记案件信息并进入扫码页</small></div><b>→</b>
          </RouterLink>
          <RouterLink
            data-action="session-list"
            class="quick-secondary"
            to="/scan-sessions"
          >
            <span>▤</span><div><strong>{{ canCreateSession ? '继续处理批次' : '查看扫描批次' }}</strong><small>查看权限范围内的进行中批次</small></div><b>→</b>
          </RouterLink>
        </section>
        <section class="info-grid">
          <article><span class="card-icon">身</span><p>当前账号</p><strong>{{ auth.user?.username }}</strong><small>{{ roleName }} · {{ branchLabel }}</small></article>
          <article><span class="card-icon">局</span><p>所属单位</p><strong>{{ branchLabel }}</strong><small>业务数据按所属分局管理</small></article>
          <article><span class="card-icon">盾</span><p>会话安全</p><strong>已保护</strong><small>关闭浏览器后请及时退出</small></article>
        </section>
        <section class="notice-card">
          <div class="notice-icon">
            i
          </div><div><h2>系统提示</h2><p>扫描批次建档功能已启用。创建批次后可进入空扫码工作区，编码识别与数量统计将在下一阶段开放。</p></div>
        </section>
      </main>
    </div>
  </div>
</template>

<style src="../styles/dashboard.css"></style>
