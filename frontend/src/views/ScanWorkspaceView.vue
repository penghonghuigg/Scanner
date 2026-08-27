<script setup lang="ts">
/* global Event, HTMLInputElement */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getScanSession, getScanState, resolveAmbiguity, scanCode } from '../api/scanSessions'
import { useAuthStore } from '../stores/auth'
import type { ProductSnapshot, ScanEvent, ScanSession, ScanState } from '../types/scanning'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const sessionId = Number(route.params.id)
const session = ref<ScanSession | null>(null)
const state = ref<ScanState | null>(null)
const scanInput = ref<HTMLInputElement | null>(null)
const code = ref('')
const requestId = ref(newRequestId())
const lastAttemptedCode = ref<string | null>(null)
const resolvingRequestIds = new Map<number, string>()
const loading = ref(true)
const submitting = ref(false)
const resolvingEventId = ref<number | null>(null)
const errorMessage = ref('')
const feedback = ref<{ kind: 'success' | 'unknown' | 'ambiguous'; text: string } | null>(null)

const canWrite = computed(() => auth.user?.role !== 'VIEWER' && session.value?.status === 'DRAFT')
const summary = computed(() => state.value?.summary ?? {
  product_count: 0, carton_count: 0, pack_count: 0,
  total_sticks: 0, unknown_count: 0, ambiguous_count: 0,
})

function newRequestId(): string {
  return globalThis.crypto.randomUUID()
}

async function focusScanner(): Promise<void> {
  if (!canWrite.value) return
  await nextTick()
  scanInput.value?.focus()
}

function productName(snapshot: ProductSnapshot | null): string {
  return snapshot?.standard_name ?? '未识别品规'
}

function successText(event: ScanEvent): string {
  const unitName = event.unit_type === 'CARTON' ? '1 条' : '1 包'
  return `识别成功：${productName(event.product_snapshot)}，本次增加 ${unitName}（${event.delta_sticks} 支）`
}

function eventResultName(event: ScanEvent): string {
  if (event.event_type === 'RESOLVE') return '歧义已解决'
  if (event.result === 'SUCCESS') return '识别成功'
  if (event.result === 'UNKNOWN') return '未识别'
  return event.resolved ? '歧义已解决' : '待处理歧义'
}

function eventUnitName(event: ScanEvent): string {
  if (event.unit_type === 'CARTON') return '条码 / 1 条'
  if (event.unit_type === 'PACK') return '包码 / 1 包'
  return '未计数'
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

async function submitScan(): Promise<void> {
  const normalizedCode = code.value.trim()
  if (normalizedCode.length !== 13 || submitting.value || !canWrite.value) return
  if (lastAttemptedCode.value !== null && lastAttemptedCode.value !== normalizedCode) {
    requestId.value = newRequestId()
  }
  lastAttemptedCode.value = normalizedCode
  submitting.value = true
  errorMessage.value = ''
  feedback.value = null
  try {
    const operation = await scanCode(sessionId, {
      request_id: requestId.value,
      code: normalizedCode,
    })
    state.value = operation.state
    if (operation.event.result === 'SUCCESS') {
      feedback.value = { kind: 'success', text: successText(operation.event) }
    } else if (operation.event.result === 'UNKNOWN') {
      feedback.value = {
        kind: 'unknown',
        text: `未识别编码：${operation.event.raw_code}，本次未计入数量`,
      }
    } else {
      feedback.value = {
        kind: 'ambiguous',
        text: `发现歧义包码：${operation.event.raw_code}，请在待处理歧义中选择品规`,
      }
    }
    code.value = ''
    requestId.value = newRequestId()
    lastAttemptedCode.value = null
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '扫码提交失败，请重试'
    await focusScanner()
  } finally {
    submitting.value = false
  }
}

function handleScanInput(event: Event): void {
  const input = event.target as HTMLInputElement
  const normalizedCode = input.value.replace(/\D/g, '').slice(0, 13)
  input.value = normalizedCode
  code.value = normalizedCode
  if (lastAttemptedCode.value !== null && lastAttemptedCode.value !== normalizedCode) {
    requestId.value = newRequestId()
    lastAttemptedCode.value = null
  }
  if (normalizedCode.length === 13) {
    void submitScan()
  }
}

async function resolveEvent(event: ScanEvent, product: ProductSnapshot): Promise<void> {
  if (resolvingEventId.value !== null || !canWrite.value) return
  resolvingEventId.value = event.id
  errorMessage.value = ''
  feedback.value = null
  const resolveRequestId = resolvingRequestIds.get(event.id) ?? newRequestId()
  resolvingRequestIds.set(event.id, resolveRequestId)
  try {
    const operation = await resolveAmbiguity(sessionId, {
      request_id: resolveRequestId,
      event_id: event.id,
      product_id: product.product_id,
    })
    state.value = operation.state
    resolvingRequestIds.delete(event.id)
    feedback.value = {
      kind: 'success',
      text: `歧义已处理：${product.standard_name}，本次增加 1 包`,
    }
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '歧义处理失败，请重试'
  } finally {
    resolvingEventId.value = null
  }
}

onMounted(async () => {
  try {
    const [sessionResult, scanState] = await Promise.all([
      getScanSession(sessionId),
      getScanState(sessionId),
    ])
    session.value = sessionResult.scan_session
    state.value = scanState
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批次扫码数据加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="scan-workspace">
    <header class="workspace-header">
      <button
        class="back-button"
        type="button"
        @click="router.push('/scan-sessions')"
      >
        ← 扫描批次
      </button>
      <span class="workspace-brand">涉案卷烟智能统计系统</span>
      <span
        v-if="session"
        class="workspace-status"
      ><i />{{ session.status_name }}</span>
    </header>

    <main
      v-if="session && state"
      class="scan-content"
    >
      <section class="scan-titlebar">
        <div><p>{{ session.session_no }} · {{ session.business_type_name }}</p><h1>{{ session.display_label }}</h1></div>
        <div class="scan-totals">
          <span><strong>{{ summary.product_count }}</strong>品规</span>
          <span><strong>{{ summary.total_sticks }}</strong>支卷烟</span>
        </div>
      </section>

      <section class="case-strip">
        <div><span>所属分局</span><strong>{{ session.branch_name }}</strong></div>
        <div><span>登记人员</span><strong>{{ session.operator_name }}</strong></div>
        <div><span>立案编号</span><strong>{{ session.filing_case_no ?? '未填写' }}</strong></div>
        <div><span>检查地点</span><strong>{{ session.location ?? '未填写' }}</strong></div>
      </section>

      <section
        v-if="canWrite"
        class="scanner-panel"
      >
        <div class="scanner-heading">
          <div>
            <p class="eyebrow">
              CONTINUOUS SCANNING
            </p><h2>扫描条码或包码</h2><span>满 13 位自动识别，处理完成会恢复焦点</span>
          </div>
          <div class="scanner-ready">
            <i />设备输入就绪
          </div>
        </div>
        <form @submit.prevent="submitScan">
          <label for="scan-code">卷烟编码</label>
          <div class="scanner-input-wrap">
            <span class="scanner-prefix">⌁</span>
            <input
              id="scan-code"
              ref="scanInput"
              v-model="code"
              name="scan_code"
              inputmode="numeric"
              autocomplete="off"
              maxlength="13"
              placeholder="请扫描或输入 13 位条码或包码"
              :disabled="submitting"
              @input="handleScanInput"
              @keydown.enter.prevent="submitScan"
            >
            <button
              type="submit"
              :disabled="submitting || code.length !== 13"
            >
              {{ submitting ? '识别中…' : '确认识别' }}
            </button>
          </div>
        </form>
      </section>
      <section
        v-else
        class="readonly-banner"
      >
        <strong>只读查看</strong><span>当前账号可以查看本批次统计，但不能提交扫码或处理歧义。</span>
      </section>

      <p
        v-if="errorMessage"
        class="scan-feedback error"
        role="alert"
      >
        <strong>提交失败</strong>{{ errorMessage }}
      </p>
      <p
        v-else-if="feedback"
        :class="['scan-feedback', feedback.kind]"
        role="status"
      >
        <strong>{{ feedback.kind === 'success' ? '处理完成' : feedback.kind === 'unknown' ? '未识别' : '需要选择' }}</strong>{{ feedback.text }}
      </p>

      <section class="scan-dashboard">
        <div class="scan-main-column">
          <section class="scan-card item-card">
            <header>
              <div>
                <p class="eyebrow">
                  LIVE SUMMARY
                </p><h2>品规实时汇总</h2>
              </div><span>{{ summary.carton_count }} 条 · {{ summary.pack_count }} 包</span>
            </header>
            <div
              v-if="!state.items.length"
              class="scan-card-empty"
            >
              尚未识别到卷烟品规，请扫描第一条编码。
            </div>
            <div
              v-else
              class="scan-item-table"
            >
              <div class="table-head">
                <span>品规</span><span>条数</span><span>包数</span><span>总支数</span>
              </div>
              <div
                v-for="item in state.items"
                :key="item.id"
                class="table-row"
              >
                <div><strong>{{ item.product_snapshot.standard_name }}</strong><small>{{ item.product_snapshot.brand }} · {{ item.product_snapshot.carton_code }}</small></div>
                <span>{{ item.carton_count }}</span><span>{{ item.pack_count }}</span><strong>{{ item.total_sticks }}</strong>
              </div>
            </div>
          </section>

          <section class="scan-card event-card">
            <header>
              <div>
                <p class="eyebrow">
                  RECENT ACTIVITY
                </p><h2>最近扫码流水</h2>
              </div><span>最近 {{ state.recent_events.length }} 条</span>
            </header>
            <div
              v-if="!state.recent_events.length"
              class="scan-card-empty"
            >
              暂无扫码流水。
            </div>
            <article
              v-for="event in state.recent_events"
              v-else
              :key="event.id"
              class="event-row"
            >
              <span :class="['event-state', event.result.toLowerCase()]">{{ eventResultName(event) }}</span>
              <div><strong>{{ event.raw_code }}</strong><small>{{ productName(event.product_snapshot) }} · {{ eventUnitName(event) }}</small></div>
              <span>{{ formatTime(event.created_at) }}</span>
            </article>
          </section>
        </div>

        <aside class="scan-side-column">
          <section class="scan-card exception-card">
            <header>
              <div>
                <p class="eyebrow">
                  EXCEPTIONS
                </p><h2>待处理歧义</h2>
              </div><span>{{ summary.ambiguous_count }}</span>
            </header>
            <div
              v-if="!state.pending_ambiguities.length"
              class="scan-card-empty compact"
            >
              当前没有待处理歧义。
            </div>
            <article
              v-for="event in state.pending_ambiguities"
              v-else
              :key="event.id"
              class="ambiguity-card"
            >
              <p>包码 <code>{{ event.raw_code }}</code></p>
              <span>请选择实际卷烟品规，选择前不会计入数量。</span>
              <button
                v-for="candidate in event.candidate_snapshot ?? []"
                :key="candidate.product_id"
                :data-action="`resolve-${event.id}-${candidate.product_id}`"
                type="button"
                :disabled="resolvingEventId !== null || !canWrite"
                @click="resolveEvent(event, candidate)"
              >
                <strong>{{ candidate.standard_name }}</strong><small>{{ candidate.brand }} · 每包 {{ candidate.sticks_per_pack }} 支</small>
              </button>
            </article>
          </section>

          <section class="scan-card metric-card">
            <header>
              <div>
                <p class="eyebrow">
                  BATCH METRICS
                </p><h2>批次统计</h2>
              </div>
            </header>
            <dl>
              <div><dt>卷烟品规</dt><dd>{{ summary.product_count }}</dd></div>
              <div><dt>累计条数</dt><dd>{{ summary.carton_count }}</dd></div>
              <div><dt>累计包数</dt><dd>{{ summary.pack_count }}</dd></div>
              <div><dt>未识别记录</dt><dd>{{ summary.unknown_count }}</dd></div>
              <div class="total">
                <dt>总卷烟数量</dt><dd>{{ summary.total_sticks }} 支</dd>
              </div>
            </dl>
          </section>
        </aside>
      </section>
    </main>

    <main
      v-else
      class="scan-content"
    >
      <p
        v-if="errorMessage"
        class="form-error"
        role="alert"
      >
        {{ errorMessage }}
      </p>
      <section
        v-else
        class="session-empty"
      >
        {{ loading ? '正在加载批次扫码数据…' : '批次扫码数据不可用' }}
      </section>
    </main>
  </div>
</template>

<style src="../styles/scanning.css"></style>
<style src="../styles/scanning-pages.css"></style>
<style scoped>
.scanner-panel,.readonly-banner,.scan-card{border:1px solid #dfe7e4;background:#fff}.scanner-panel{padding:27px 30px;border-top:0}.scanner-heading{margin-bottom:19px;display:flex;align-items:flex-end;justify-content:space-between;gap:20px}.scanner-heading h2,.scan-card h2{margin:5px 0;font-size:18px}.scanner-heading span{color:#7b8884;font-size:12px}.scanner-ready{padding:8px 11px;border-radius:20px;color:#176150;background:#edf7f3;font-size:11px}.scanner-ready i{display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:#2a9a79}.scanner-panel form label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.scanner-input-wrap{height:64px;display:grid;grid-template-columns:52px 1fr auto;border:2px solid #1c6657;border-radius:10px;overflow:hidden;box-shadow:0 0 0 4px #1c66570e}.scanner-prefix{display:grid;place-items:center;color:#c58d38;background:#f3f8f6;font-size:25px}.scanner-input-wrap input{min-width:0;padding:0 8px;border:0;outline:0;font-size:21px;letter-spacing:.08em}.scanner-input-wrap button{margin:7px;padding:0 22px;border:0;border-radius:7px;color:#fff;background:#174d43;font-weight:700}.scanner-input-wrap button:disabled{opacity:.55}.readonly-banner{padding:18px 26px;display:flex;gap:12px;border-top:0;color:#697671}.readonly-banner strong{color:#173f37}.scan-feedback{margin:14px 0 0;padding:14px 18px;border:1px solid;border-radius:9px;font-size:13px}.scan-feedback strong{margin-right:10px}.scan-feedback.success{border-color:#b9dacd;color:#175d4d;background:#eef8f4}.scan-feedback.unknown{border-color:#e8d1a8;color:#7b571c;background:#fff8e9}.scan-feedback.ambiguous{border-color:#dcc49a;color:#76511a;background:#fff7e7}.scan-feedback.error{border-color:#e3bdb7;color:#8c3c31;background:#fff2f0}.scan-dashboard{margin-top:16px;display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:16px}.scan-main-column,.scan-side-column{display:grid;gap:16px;align-content:start}.scan-card{overflow:hidden;border-radius:11px}.scan-card>header{padding:18px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e8eeec}.scan-card>header p{margin:0}.scan-card>header span{color:#778580;font-size:11px}.scan-card-empty{padding:38px 20px;color:#84908c;text-align:center;font-size:12px}.scan-card-empty.compact{padding:25px 18px}.table-head,.table-row{display:grid;grid-template-columns:minmax(220px,1fr) 70px 70px 82px;gap:12px;align-items:center}.table-head{padding:11px 20px;color:#86928e;background:#f7f9f8;font-size:10px}.table-row{padding:17px 20px}.table-row+.table-row{border-top:1px solid #edf1ef}.table-row>div strong,.table-row>div small{display:block}.table-row>div small{margin-top:6px;color:#85918d;font-size:10px}.table-row>span,.table-row>strong{text-align:center}.event-row{padding:14px 18px;display:grid;grid-template-columns:82px 1fr auto;gap:12px;align-items:center}.event-row+.event-row{border-top:1px solid #edf1ef}.event-row>div strong,.event-row>div small{display:block}.event-row>div small{margin-top:5px;color:#89938f;font-size:10px}.event-row>span:last-child{color:#89938f;font-size:10px}.event-state{padding:5px 7px;border-radius:5px;text-align:center;font-size:10px}.event-state.success{color:#17614f;background:#eaf6f1}.event-state.unknown{color:#8b5d17;background:#fff3dc}.event-state.ambiguous{color:#8a4e26;background:#fff0e4}.ambiguity-card{padding:16px 18px}.ambiguity-card+.ambiguity-card{border-top:1px solid #e8eeec}.ambiguity-card p{margin:0 0 7px;font-size:12px}.ambiguity-card>span{display:block;margin-bottom:12px;color:#84908c;font-size:11px;line-height:1.6}.ambiguity-card button{width:100%;margin-top:8px;padding:11px 12px;border:1px solid #d9e3df;border-radius:7px;color:#24342f;background:#fff;text-align:left}.ambiguity-card button:hover:not(:disabled){border-color:#3d8374;background:#f4f9f7}.ambiguity-card button strong,.ambiguity-card button small{display:block}.ambiguity-card button small{margin-top:5px;color:#87928e}.metric-card dl{margin:0;padding:5px 18px 17px}.metric-card dl>div{padding:12px 2px;display:flex;justify-content:space-between;border-bottom:1px solid #edf1ef}.metric-card dt{color:#7d8985;font-size:12px}.metric-card dd{margin:0;font-weight:800}.metric-card .total{margin-top:7px;padding:15px 13px;border:0;border-radius:7px;color:#fff;background:#123c34}.metric-card .total dt{color:#ffffffa3}@media(max-width:980px){.scan-dashboard{grid-template-columns:1fr}.scan-side-column{grid-template-columns:1fr 1fr}}@media(max-width:640px){.scanner-panel{padding:22px 16px}.scanner-heading{align-items:flex-start;flex-direction:column}.scanner-input-wrap{height:auto;grid-template-columns:42px 1fr}.scanner-input-wrap input{height:58px;font-size:16px}.scanner-input-wrap button{grid-column:1/-1;height:44px;margin:0 7px 7px}.scan-side-column{grid-template-columns:1fr}.table-head,.table-row{grid-template-columns:1fr 45px 45px 60px;padding-left:12px;padding-right:12px}.event-row{grid-template-columns:75px 1fr}.event-row>span:last-child{display:none}}
</style>
