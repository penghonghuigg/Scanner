<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createScanSession } from '../api/scanSessions'
import { ApiRequestError } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { BRANCH_NAMES, BRANCH_VALUES, type BranchCode } from '../types/auth'
import { BUSINESS_TYPES, type BusinessType } from '../types/scanning'

const auth = useAuthStore()
const router = useRouter()
const businessType = ref<BusinessType | ''>('')
const filingCaseNo = ref('')
const location = ref('')
const notes = ref('')
const branchCode = ref<BranchCode | ''>('')
const submitting = ref(false)
const errorMessage = ref('')

const isAdmin = computed(() => auth.user?.role === 'ADMIN')
const branchLabel = computed(() => isAdmin.value
  ? (branchCode.value ? BRANCH_NAMES[branchCode.value] : '待选择所属分局')
  : (auth.user?.branch_name ?? '未配置所属分局'))
const displayPreview = computed(() => {
  const now = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date()).replace(/\//g, '-')
  return `${now}—${auth.user?.display_name ?? ''}—0个品规—0支卷烟`
})

function optional(value: string): string | undefined {
  return value.trim() || undefined
}

async function submit(): Promise<void> {
  if (!businessType.value || (isAdmin.value && !branchCode.value)) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await createScanSession({
      business_type: businessType.value,
      filing_case_no: optional(filingCaseNo.value),
      location: optional(location.value),
      notes: optional(notes.value),
      branch_code: isAdmin.value ? branchCode.value || undefined : undefined,
    })
    await router.push(`/scan-sessions/${result.scan_session.id}/scan`)
  } catch (error) {
    errorMessage.value = error instanceof ApiRequestError ? error.message : '批次创建失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="session-page">
    <header class="session-topbar">
      <button
        class="back-button"
        type="button"
        @click="router.push('/')"
      >
        ← 返回工作台
      </button>
      <div><strong>涉案卷烟智能统计系统</strong><span>批次建档</span></div>
      <span class="topbar-user">{{ auth.user?.display_name }} · {{ auth.user?.branch_name ?? '系统管理' }}</span>
    </header>

    <main class="session-create-layout">
      <section class="session-form-panel">
        <p class="eyebrow">
          NEW SCAN SESSION
        </p>
        <h1>新建扫描批次</h1>
        <p class="session-lead">
          先登记本次业务基本信息，创建后即可进入扫码工作区。
        </p>

        <ol
          class="process-rail"
          aria-label="批次业务流程"
        >
          <li class="current">
            <span>01</span>批次建档
          </li>
          <li><span>02</span>扫码统计</li>
          <li><span>03</span>核对导出</li>
        </ol>

        <form
          data-form="scan-session"
          @submit.prevent="submit"
        >
          <fieldset class="business-fieldset">
            <legend>业务类型 <em>必填</em></legend>
            <div class="business-options">
              <label
                v-for="item in BUSINESS_TYPES"
                :key="item.value"
                :class="{ selected: businessType === item.value }"
              >
                <input
                  v-model="businessType"
                  type="radio"
                  name="business_type"
                  :value="item.value"
                  required
                >
                <span class="choice-mark" />
                <strong>{{ item.label }}</strong>
                <small>{{ item.description }}</small>
              </label>
            </div>
          </fieldset>

          <div class="session-fields">
            <label v-if="isAdmin">所属分局 <em>必填</em>
              <select
                v-model="branchCode"
                name="branch_code"
                required
              >
                <option
                  value=""
                  disabled
                >请选择所属分局</option>
                <option
                  v-for="code in BRANCH_VALUES"
                  :key="code"
                  :value="code"
                >{{ BRANCH_NAMES[code] }}</option>
              </select>
            </label>
            <label v-else>所属分局
              <span
                class="readonly-field"
                data-field="branch-readonly"
              >{{ branchLabel }}<small>根据当前账号自动确定</small></span>
            </label>
            <label>立案编号 <span>选填</span>
              <input
                v-model="filingCaseNo"
                name="filing_case_no"
                maxlength="100"
                placeholder="如：凤烟立〔2026〕001号"
              >
            </label>
            <label>检查地点 <span>选填</span>
              <input
                v-model="location"
                name="location"
                maxlength="200"
                placeholder="填写现场或案件地点"
              >
            </label>
            <label class="wide-field">备注 <span>选填</span>
              <textarea
                v-model="notes"
                name="notes"
                maxlength="500"
                rows="4"
                placeholder="可补充记录本次业务的说明"
              />
            </label>
          </div>

          <p
            v-if="errorMessage"
            class="form-error"
            role="alert"
          >
            {{ errorMessage }}
          </p>
          <div class="session-actions">
            <p>创建后处于“进行中”状态，不会自动完成批次。</p>
            <button
              type="submit"
              :disabled="submitting || !businessType || (isAdmin && !branchCode)"
            >
              {{ submitting ? '正在创建…' : '创建并进入扫码页' }} <span>→</span>
            </button>
          </div>
        </form>
      </section>

      <aside class="session-docket">
        <p class="docket-kicker">
          BATCH PLATE / 批次铭牌
        </p>
        <div class="docket-number">
          批次编号将在创建后生成
        </div>
        <dl>
          <div><dt>登记人员</dt><dd>{{ auth.user?.display_name }}</dd></div>
          <div><dt>所属分局</dt><dd>{{ branchLabel }}</dd></div>
          <div><dt>当前状态</dt><dd><span class="draft-dot" />进行中</dd></div>
        </dl>
        <div class="docket-label">
          <span>列表标识预览</span><strong>{{ displayPreview }}</strong>
        </div>
        <p class="docket-tip">
          品规数和卷烟总量将在后续扫码过程中由系统自动累计。
        </p>
      </aside>
    </main>
  </div>
</template>

<style src="../styles/scanning.css"></style>
<style>
@media (max-width: 960px) {
  .session-docket { position: relative; }
}
</style>
