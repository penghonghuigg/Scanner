<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiRequestError } from '../api/http'
import { listScanSessions } from '../api/scanSessions'
import AppSidebar from '../components/AppSidebar.vue'
import { useAuthStore } from '../stores/auth'
import type { ScanSession } from '../types/scanning'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const items = ref<ScanSession[]>([])
const total = ref(0)
const query = ref('')
const loading = ref(true)
const errorMessage = ref('')
const sessionStatus = computed<'DRAFT' | 'COMPLETED'>(() => (
  route.meta.sessionStatus === 'COMPLETED' ? 'COMPLETED' : 'DRAFT'
))
const resultMode = computed(() => sessionStatus.value === 'COMPLETED')

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const filters: Parameters<typeof listScanSessions>[0] = {
      status: sessionStatus.value, page: 1, page_size: 20,
    }
    const normalizedQuery = query.value.trim()
    if (normalizedQuery) filters.query = normalizedQuery
    const result = await listScanSessions(filters)
    items.value = result.items
    total.value = result.total
  } catch (error) {
    errorMessage.value = error instanceof ApiRequestError ? error.message : '批次列表加载失败'
  } finally {
    loading.value = false
  }
}

function openSession(item: ScanSession): void {
  router.push(resultMode.value ? `/scan-results/${item.id}` : `/scan-sessions/${item.id}/scan`)
}

async function resetQuery(): Promise<void> {
  query.value = ''
  await load()
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

watch(sessionStatus, load, { immediate: true })
</script>

<template>
  <div class="workspace-shell">
    <AppSidebar />
    <div class="workspace-main session-page">
      <header class="session-topbar">
        <button
          class="back-button"
          type="button"
          @click="router.push('/')"
        >
          ← 返回工作台
        </button>
        <div><strong>涉案卷烟智能统计系统</strong><span>{{ resultMode ? '结果中心' : '作业中心' }}</span></div>
        <span class="topbar-user">{{ auth.user?.display_name }} · {{ auth.user?.branch_name ?? '系统管理' }}</span>
      </header>
      <main class="session-list-page">
        <div class="list-heading">
          <div>
            <p class="eyebrow">
              {{ resultMode ? 'COMPLETED INVENTORY' : 'INVENTORY OPERATIONS' }}
            </p><h1>{{ resultMode ? '盘点结果' : '盘点作业' }}</h1><p>{{ resultMode ? '查看和维护权限范围内已经完成的盘点结果。' : '查看权限范围内尚未完成的盘点作业。' }}</p>
          </div>
          <RouterLink
            v-if="!resultMode && auth.user?.role !== 'VIEWER'"
            class="primary-link"
            to="/scan-sessions/new"
          >
            ＋ 新建盘点作业
          </RouterLink>
        </div>
        <form
          class="session-searchbar"
          role="search"
          @submit.prevent="load"
        >
          <label>
            <span>{{ resultMode ? '检索结果' : '检索作业' }}</span>
            <input
              v-model="query"
              name="session_query"
              maxlength="100"
              autocomplete="off"
              placeholder="输入批次编号、立案编号或地点"
              @keyup.enter="load"
            >
          </label>
          <button
            class="search-primary"
            type="submit"
          >
            查询
          </button>
          <button
            data-action="reset-session-query"
            type="button"
            @click="resetQuery"
          >
            重置
          </button>
          <div class="session-search-summary">
            <span class="draft-dot" />{{ resultMode ? '已完成结果' : '进行中作业' }} <small>共 {{ total }} 条</small>
          </div>
        </form>
        <p
          v-if="errorMessage"
          class="form-error"
          role="alert"
        >
          {{ errorMessage }}
        </p>
        <section
          v-if="loading"
          class="session-empty"
        >
          正在加载批次…
        </section>
        <section
          v-else-if="!items.length"
          class="session-empty"
        >
          <strong>{{ resultMode ? '暂无已完成结果' : '暂无进行中作业' }}</strong><p>{{ resultMode ? '完成盘点作业后，结果将在这里显示。' : '新建一个盘点作业后，将在这里继续处理。' }}</p>
        </section>
        <section
          v-else
          class="session-table-card"
        >
          <article
            v-for="item in items"
            :key="item.id"
            class="session-row"
            @click="openSession(item)"
          >
            <div class="row-date">
              <strong>{{ formatTime(item.created_at) }}</strong><small>{{ item.session_no }}</small>
            </div>
            <div class="row-main">
              <h2>{{ item.display_label }}</h2><p>{{ item.business_type_name }} · {{ item.branch_name }}<span v-if="item.filing_case_no"> · {{ item.filing_case_no }}</span></p>
            </div>
            <div class="row-count">
              <strong>{{ item.product_count }}</strong><small>品规</small>
            </div>
            <div class="row-count">
              <strong>{{ item.total_sticks }}</strong><small>卷烟（支）</small>
            </div>
            <div class="row-status">
              <span class="draft-dot" />{{ item.status_name }}
            </div><span class="row-arrow">→</span>
          </article>
        </section>
      </main>
    </div>
  </div>
</template>

<style src="../styles/scanning.css"></style>
<style src="../styles/scanning-pages.css"></style>
<style scoped>
.session-searchbar{margin-bottom:14px;padding:16px;display:grid;grid-template-columns:minmax(280px,1fr) auto auto auto;gap:10px;align-items:end;border:1px solid #dfe7e4;border-radius:11px;background:#fff;box-shadow:0 10px 28px #123c3408}.session-searchbar label{display:grid;gap:7px;color:#66736f;font-size:11px}.session-searchbar input{height:40px;padding:0 13px;border:1px solid #ced9d5;border-radius:7px;outline:0;color:#24312d;background:#fbfcfc}.session-searchbar input:focus{border-color:#277564;box-shadow:0 0 0 3px #27756414}.session-searchbar button{height:40px;padding:0 17px;border:1px solid #d3deda;border-radius:7px;color:#46534f;background:#fff;font-weight:700}.session-searchbar .search-primary{border-color:#174d43;color:#fff;background:#174d43}.session-search-summary{min-width:170px;height:40px;display:flex;align-items:center;justify-content:flex-end;color:#53615c;font-size:12px}.session-search-summary small{margin-left:9px;color:#87928e}@media(max-width:640px){.session-searchbar{grid-template-columns:1fr 1fr}.session-searchbar label,.session-search-summary{grid-column:1/-1}.session-search-summary{justify-content:flex-start}}
</style>
