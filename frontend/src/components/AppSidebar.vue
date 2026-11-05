<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const canManage = computed(() => auth.user?.role === 'ADMIN')

function active(prefix: string): boolean {
  if (prefix === '/') return route.path === '/'
  return route.path === prefix || route.path.startsWith(`${prefix}/`)
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <span class="sidebar-logo">案</span><span>涉案卷烟<br><small>智能统计系统</small></span>
    </div>
    <nav aria-label="主导航">
      <RouterLink
        class="nav-item"
        :class="{ active: active('/') }"
        to="/"
      >
        <span>⌂</span>系统首页
      </RouterLink>
      <RouterLink
        class="nav-item"
        :class="{ active: active('/scan-sessions') }"
        to="/scan-sessions"
      >
        <span>▤</span>盘点作业
      </RouterLink>
      <RouterLink
        class="nav-item"
        :class="{ active: active('/scan-results') }"
        to="/scan-results"
      >
        <span>✓</span>盘点结果
      </RouterLink>
      <RouterLink
        v-if="canManage"
        class="nav-item"
        :class="{ active: active('/users/register') }"
        to="/users/register"
      >
        <span>＋</span>人员注册
      </RouterLink>
      <RouterLink
        v-if="canManage"
        class="nav-item"
        :class="{ active: active('/products') }"
        to="/products"
      >
        <span>▦</span>品规管理
      </RouterLink>
    </nav>
    <div class="sidebar-version">
      内部业务系统<br>Version 0.1.0
    </div>
  </aside>
</template>
