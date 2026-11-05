<script setup lang="ts">
/* global Event, HTMLInputElement, URL, document */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  addResultItem,
  adjustCartonQuantity,
  completeScanSession,
  downloadScanSessionExport,
  getRegionCatalog,
  getIntegrationSnapshot,
  getScanSession,
  getScanState,
  getSourceAllocations,
  importToJianDaoYun,
  listScanEvents,
  removeScanSessionItem,
  replaceResultItem,
  replaceSourceAllocations,
  resolveAmbiguity,
  scanCode,
} from '../api/scanSessions'
import AdjustmentReasonDialog from '../components/scanning/AdjustmentReasonDialog.vue'
import CompletionPanel from '../components/scanning/CompletionPanel.vue'
import InventorySummaryCards from '../components/scanning/InventorySummaryCards.vue'
import LatestRecognitionCard from '../components/scanning/LatestRecognitionCard.vue'
import ProductQuantityTable from '../components/scanning/ProductQuantityTable.vue'
import ResultItemEditorDialog from '../components/scanning/ResultItemEditorDialog.vue'
import ScanEventHistory from '../components/scanning/ScanEventHistory.vue'
import SourceAllocationDialog from '../components/scanning/SourceAllocationDialog.vue'
import { useAuthStore } from '../stores/auth'
import type {
  AdjustmentReasonType,
  IntegrationSnapshot,
  ProductSnapshot,
  ProductOption,
  ProductSourceAllocationState,
  RegionCatalog,
  ScanEvent,
  ScanEventPage,
  ScanSession,
  ScanSessionItem,
  ScanState,
  SourceAllocationInput,
} from '../types/scanning'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const sessionId = Number(route.params.id)
const session = ref<ScanSession | null>(null)
const state = ref<ScanState | null>(null)
const eventPage = ref<ScanEventPage>({ items: [], total: 0, page: 1, page_size: 10 })
const regionCatalog = ref<RegionCatalog>({ source_types: [], provinces: [] })
const sourceStates = ref<ProductSourceAllocationState[]>([])
const selectedSourceState = ref<ProductSourceAllocationState | null>(null)
const resultEditorOpen = ref(false)
const resultEditorItem = ref<ScanSessionItem | null>(null)
const pendingResult = ref<{ product: ProductOption; quantity: number; editing: boolean } | null>(null)
const pendingAdjustment = ref<{
  item: ScanSessionItem
  operation: 'DELTA' | 'SET'
  quantity: number
} | null>(null)
const scanInput = ref<HTMLInputElement | null>(null)
const code = ref('')
const requestId = ref(newRequestId())
const lastAttemptedCode = ref<string | null>(null)
const resolvingRequestIds = new Map<number, string>()
const adjustmentRequestIds = new Map<string, string>()
const removalRequestIds = new Map<number, string>()
const resultRequestIds = new Map<string, string>()
const loading = ref(true)
const eventLoading = ref(false)
const submitting = ref(false)
const resolvingEventId = ref<number | null>(null)
const adjustingProductId = ref<number | null>(null)
const removingProductId = ref<number | null>(null)
const savingSources = ref(false)
const completing = ref(false)
const downloading = ref(false)
const importing = ref(false)
const integrationSnapshot = ref<IntegrationSnapshot | null>(null)
const errorMessage = ref('')
const feedback = ref<{ kind: 'success' | 'unknown' | 'ambiguous'; text: string } | null>(null)

const canWrite = computed(() => auth.user?.role !== 'VIEWER')
const canScan = computed(() => canWrite.value && session.value?.status === 'DRAFT')
const canEditResult = computed(() => canWrite.value && session.value?.status === 'COMPLETED')
const summary = computed(() => state.value?.summary ?? {
  product_count: 0,
  carton_count: 0,
  pack_count: 0,
  total_sticks: 0,
  unknown_count: 0,
  ambiguous_count: 0,
})
const catalogSummary = computed(() => state.value?.catalog_summary ?? {
  active_code_count: 0,
  active_standard_product_count: 0,
})

function newRequestId(): string {
  return globalThis.crypto.randomUUID()
}

async function focusScanner(): Promise<void> {
  if (!canScan.value) return
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

async function loadEventPage(page: number): Promise<void> {
  eventLoading.value = true
  try {
    eventPage.value = await listScanEvents(sessionId, { page, page_size: 10 })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '扫码流水加载失败'
  } finally {
    eventLoading.value = false
  }
}

async function submitScan(): Promise<void> {
  const normalizedCode = code.value.trim()
  if (!/^\d{6,64}$/.test(normalizedCode) || submitting.value || !canScan.value) return
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
    submitting.value = false
    await focusScanner()
    await Promise.all([loadEventPage(1), refreshSourceAllocations()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '扫码提交失败，请重试'
    submitting.value = false
    await focusScanner()
  } finally {
    submitting.value = false
  }
}

function handleScanInput(event: Event): void {
  const input = event.target as HTMLInputElement
  const normalizedCode = input.value.replace(/\D/g, '').slice(0, 64)
  input.value = normalizedCode
  code.value = normalizedCode
  if (lastAttemptedCode.value !== null && lastAttemptedCode.value !== normalizedCode) {
    requestId.value = newRequestId()
    lastAttemptedCode.value = null
  }
}

async function resolveEvent(event: ScanEvent, product: ProductSnapshot): Promise<void> {
  if (resolvingEventId.value !== null || !canScan.value) return
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
    feedback.value = { kind: 'success', text: `歧义已处理：${product.standard_name}，本次增加 1 包` }
    await Promise.all([loadEventPage(1), refreshSourceAllocations()])
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '歧义处理失败，请重试'
  } finally {
    resolvingEventId.value = null
  }
}

function requestAdjustment(payload: {
  productId: number
  operation: 'DELTA' | 'SET'
  quantity: number
}): void {
  const item = state.value?.items.find((candidate) => candidate.product_id === payload.productId)
  if (!item || !canScan.value) return
  pendingAdjustment.value = { item, operation: payload.operation, quantity: payload.quantity }
}

async function submitAdjustment(reason: {
  reasonType: AdjustmentReasonType
  reasonNote: string
}): Promise<void> {
  const payload = pendingAdjustment.value
  if (!payload) return
  const productId = payload.item.product_id
  if (adjustingProductId.value !== null || !canScan.value) return
  adjustingProductId.value = productId
  errorMessage.value = ''
  feedback.value = null
  const key = `${productId}:${payload.operation}:${payload.quantity}:${reason.reasonType}:${reason.reasonNote}`
  const adjustmentRequestId = adjustmentRequestIds.get(key) ?? newRequestId()
  adjustmentRequestIds.set(key, adjustmentRequestId)
  try {
    const operation = await adjustCartonQuantity(sessionId, productId, {
      request_id: adjustmentRequestId,
      operation: payload.operation,
      quantity: payload.quantity,
      reason_type: reason.reasonType,
      reason_note: reason.reasonNote,
    })
    state.value = operation.state
    adjustmentRequestIds.delete(key)
    pendingAdjustment.value = null
    feedback.value = { kind: 'success', text: operation.event.reason ?? '条数调整完成' }
    await loadEventPage(1)
    await refreshSourceAllocations()
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '条数调整失败，请重试'
  } finally {
    adjustingProductId.value = null
  }
}

async function refreshSourceAllocations(): Promise<void> {
  sourceStates.value = (await getSourceAllocations(sessionId)).items
}

function openResultEditor(item: ScanSessionItem | null = null): void {
  if (!canEditResult.value) return
  resultEditorItem.value = item
  resultEditorOpen.value = true
}

function continueResultEdit(payload: { product: ProductOption; quantity: number }): void {
  const editing = resultEditorItem.value !== null
  const currentSource = editing
    ? sourceStates.value.find((candidate) => candidate.product_id === payload.product.id)
    : null
  pendingResult.value = { ...payload, editing }
  resultEditorOpen.value = false
  selectedSourceState.value = {
    product_id: payload.product.id,
    product_snapshot: {
      product_id: payload.product.id,
      carton_code: payload.product.carton_code,
      pack_code: null,
      brand: payload.product.brand,
      standard_name: payload.product.standard_name,
      carton_retail_price: payload.product.carton_retail_price,
      sticks_per_pack: payload.product.sticks_per_pack,
      packs_per_carton: payload.product.packs_per_carton,
      sticks_per_carton: payload.product.sticks_per_pack * payload.product.packs_per_carton,
    },
    required_pack_count: Math.round(payload.quantity * payload.product.packs_per_carton),
    allocated_pack_count: currentSource?.allocated_pack_count ?? 0,
    remaining_pack_count: Math.round(payload.quantity * payload.product.packs_per_carton)
      - (currentSource?.allocated_pack_count ?? 0),
    allocations: currentSource?.allocations ?? [],
  }
}

async function refreshResultState(): Promise<void> {
  const [scanState, sources] = await Promise.all([
    getScanState(sessionId),
    getSourceAllocations(sessionId),
  ])
  state.value = scanState
  sourceStates.value = sources.items
  await loadEventPage(1)
}

function openSourceAllocation(item: ScanSessionItem): void {
  selectedSourceState.value = sourceStates.value.find(
    (candidate) => candidate.product_id === item.product_id,
  ) ?? null
}

function cancelSourceDialog(): void {
  selectedSourceState.value = null
  pendingResult.value = null
}

async function saveSourceAllocations(items: SourceAllocationInput[]): Promise<void> {
  const selected = selectedSourceState.value
  if (!selected || savingSources.value) return
  savingSources.value = true
  errorMessage.value = ''
  try {
    if (pendingResult.value) {
      const pending = pendingResult.value
      const key = `${pending.editing ? 'replace' : 'add'}:${pending.product.id}:${pending.quantity}`
      const operationRequestId = resultRequestIds.get(key) ?? newRequestId()
      resultRequestIds.set(key, operationRequestId)
      if (pending.editing) {
        await replaceResultItem(sessionId, pending.product.id, {
          request_id: operationRequestId,
          quantity_cartons: pending.quantity,
          source_allocations: items,
        })
      } else {
        await addResultItem(sessionId, {
          request_id: operationRequestId,
          product_id: pending.product.id,
          quantity_cartons: pending.quantity,
          source_allocations: items,
        })
      }
      resultRequestIds.delete(key)
      pendingResult.value = null
      selectedSourceState.value = null
      resultEditorItem.value = null
      await refreshResultState()
      feedback.value = { kind: 'success', text: '已完成盘点结果已更新' }
      return
    }
    const updated = await replaceSourceAllocations(sessionId, selected.product_id, { items })
    const index = sourceStates.value.findIndex((item) => item.product_id === updated.product_id)
    if (index >= 0) sourceStates.value[index] = updated
    else sourceStates.value.push(updated)
    selectedSourceState.value = null
    feedback.value = { kind: 'success', text: '卷烟来源拆分已保存' }
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '来源拆分保存失败'
  } finally {
    savingSources.value = false
  }
}

async function finishSession(confirmExceptions: boolean): Promise<void> {
  if (!session.value || completing.value) return
  completing.value = true
  errorMessage.value = ''
  try {
    const result = await completeScanSession(sessionId, {
      confirm_exceptions: confirmExceptions,
    })
    session.value = result.scan_session
    if (state.value) state.value.summary = result.summary
    feedback.value = { kind: 'success', text: '批次已完成，数据已封存为只读状态' }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批次完成失败'
  } finally {
    completing.value = false
  }
}

async function downloadExcel(): Promise<void> {
  downloading.value = true
  errorMessage.value = ''
  try {
    const file = await downloadScanSessionExport(sessionId)
    if (typeof URL.createObjectURL === 'function') {
      const url = URL.createObjectURL(file.blob)
      const link = document.createElement('a')
      link.href = url
      link.download = file.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    }
    feedback.value = { kind: 'success', text: `Excel 已生成：${file.filename}` }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Excel 导出失败'
  } finally {
    downloading.value = false
  }
}

async function importJiandaoyun(): Promise<void> {
  if (importing.value || session.value?.status !== 'COMPLETED') return
  importing.value = true
  errorMessage.value = ''
  try {
    const result = await importToJianDaoYun(sessionId)
    integrationSnapshot.value = result.snapshot
    feedback.value = { kind: 'success', text: '盘点结果已导入简道云' }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '简道云导入失败'
    try {
      integrationSnapshot.value = (await getIntegrationSnapshot(sessionId)).snapshot
    } catch {
      // 保留原错误；状态可在刷新页面后重新获取。
    }
  } finally {
    importing.value = false
  }
}

async function removeItem(item: ScanSessionItem): Promise<void> {
  if (removingProductId.value !== null || !canWrite.value) return
  removingProductId.value = item.product_id
  errorMessage.value = ''
  feedback.value = null
  const removalRequestId = removalRequestIds.get(item.product_id) ?? newRequestId()
  removalRequestIds.set(item.product_id, removalRequestId)
  try {
    const operation = await removeScanSessionItem(sessionId, item.product_id, {
      request_id: removalRequestId,
    })
    state.value = operation.state
    removalRequestIds.delete(item.product_id)
    feedback.value = {
      kind: 'success',
      text: operation.event.reason ?? '品规已从当前批次统计中移除',
    }
    await Promise.all([loadEventPage(1), refreshSourceAllocations()])
    await focusScanner()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '品规删除失败，请重试'
  } finally {
    removingProductId.value = null
  }
}

onMounted(async () => {
  try {
    const [sessionResult, scanState, , regions, sources, integration] = await Promise.all([
      getScanSession(sessionId),
      getScanState(sessionId),
      loadEventPage(1),
      getRegionCatalog(),
      getSourceAllocations(sessionId),
      getIntegrationSnapshot(sessionId),
    ])
    session.value = sessionResult.scan_session
    state.value = scanState
    regionCatalog.value = regions
    sourceStates.value = sources.items
    integrationSnapshot.value = integration.snapshot
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
        @click="router.push(session?.status === 'COMPLETED' ? '/scan-results' : '/scan-sessions')"
      >
        ← {{ session?.status === 'COMPLETED' ? '盘点结果' : '盘点作业' }}
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

      <InventorySummaryCards
        :items="state.items"
        :unknown-count="summary.unknown_count"
      />

      <section class="scan-entry-grid">
        <section
          v-if="canScan"
          class="scanner-panel"
        >
          <div class="scanner-heading">
            <div>
              <p class="eyebrow">
                SCANNER INPUT
              </p>
              <h2>扫码录入</h2>
              <span>扫描条码或包码，扫码枪回车或点击确认后识别</span>
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
                maxlength="64"
                placeholder="请扫描或输入条码、包码后按回车"
                :disabled="submitting"
                @input="handleScanInput"
                @keydown.enter.prevent="submitScan"
              >
              <button
                type="submit"
                :disabled="submitting || !/^\d{6,64}$/.test(code)"
              >
                {{ submitting ? '识别中…' : '确认识别' }}
              </button>
            </div>
          </form>
          <p class="catalog-hint">
            基础库：{{ catalogSummary.active_code_count }} 个编码 / {{ catalogSummary.active_standard_product_count }} 个标准品规
          </p>
        </section>
        <section
          v-else
          class="readonly-banner"
        >
          <strong>{{ canEditResult ? '已完成结果修订' : '只读查看' }}</strong>
          <span v-if="canEditResult">已禁止继续扫码；可从品规库增加卷烟，或修订现有数量和来源地，全部操作保留流水。</span>
          <span v-else>当前账号可以查看本批次统计，但不能提交扫码、调整数量或处理歧义。</span>
          <button
            v-if="canEditResult"
            data-action="add-result-item"
            type="button"
            @click="openResultEditor()"
          >
            从品规库增加卷烟
          </button>
        </section>
        <LatestRecognitionCard :event="state.latest_successful_event ?? null" />
      </section>

      <p
        v-if="errorMessage"
        class="scan-feedback error"
        role="alert"
      >
        <strong>操作失败</strong>{{ errorMessage }}
      </p>
      <p
        v-else-if="feedback"
        :class="['scan-feedback', feedback.kind]"
        role="status"
      >
        <strong>{{ feedback.kind === 'success' ? '处理完成' : feedback.kind === 'unknown' ? '未识别' : '需要选择' }}</strong>{{ feedback.text }}
      </p>

      <ProductQuantityTable
        :items="state.items"
        :can-write="canWrite"
        :completed="session.status === 'COMPLETED'"
        :adjusting-product-id="adjustingProductId"
        :removing-product-id="removingProductId"
        @adjust="requestAdjustment"
        @allocate="openSourceAllocation"
        @remove="removeItem"
        @edit="openResultEditor"
      />

      <CompletionPanel
        :status="session.status"
        :can-write="canWrite"
        :source-states="sourceStates"
        :unknown-count="summary.unknown_count"
        :ambiguity-count="summary.ambiguous_count"
        :completing="completing"
        :downloading="downloading"
        :importing="importing"
        :integration-snapshot="integrationSnapshot"
        @complete="finishSession"
        @download="downloadExcel"
        @import-jiandaoyun="importJiandaoyun"
      />

      <section class="activity-grid">
        <ScanEventHistory
          :page="eventPage"
          :loading="eventLoading"
          @page-change="loadEventPage"
        />
        <section class="exception-panel">
          <header><div><span>EXCEPTIONS</span><h2>待处理歧义</h2></div><strong>{{ summary.ambiguous_count }}</strong></header>
          <div
            v-if="!state.pending_ambiguities.length"
            class="exception-empty"
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
            <span>请选择实际卷烟品规，选择前不计入数量。</span>
            <button
              v-for="candidate in event.candidate_snapshot ?? []"
              :key="candidate.product_id"
              :data-action="`resolve-${event.id}-${candidate.product_id}`"
              type="button"
              :disabled="resolvingEventId !== null || !canScan"
              @click="resolveEvent(event, candidate)"
            >
              <strong>{{ candidate.standard_name }}</strong>
              <small>{{ candidate.brand }} · 每包 {{ candidate.sticks_per_pack }} 支</small>
            </button>
          </article>
        </section>
      </section>

      <AdjustmentReasonDialog
        :item="pendingAdjustment?.item ?? null"
        :operation="pendingAdjustment?.operation ?? 'DELTA'"
        :quantity="pendingAdjustment?.quantity ?? 0"
        :submitting="adjustingProductId !== null"
        @cancel="pendingAdjustment = null"
        @confirm="submitAdjustment"
      />
      <SourceAllocationDialog
        :state="selectedSourceState"
        :catalog="regionCatalog"
        :saving="savingSources"
        @cancel="cancelSourceDialog"
        @save="saveSourceAllocations"
      />
      <ResultItemEditorDialog
        :open="resultEditorOpen"
        :item="resultEditorItem"
        @cancel="resultEditorOpen = false"
        @continue="continueResultEdit"
      />
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
.scan-entry-grid,.activity-grid{margin-top:16px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(340px,.75fr);gap:16px;align-items:stretch}.scanner-panel,.readonly-banner,.exception-panel{border:1px solid #dfe7e4;background:#fff}.scanner-panel{padding:24px 26px}.scanner-heading{margin-bottom:18px;display:flex;align-items:flex-end;justify-content:space-between;gap:20px}.eyebrow,.exception-panel header span{margin:0;color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.scanner-heading h2,.exception-panel h2{margin:5px 0;color:#1d312b;font-size:18px}.scanner-heading span{color:#7b8884;font-size:11px}.scanner-ready{padding:8px 11px;border-radius:20px;color:#176150;background:#edf7f3;font-size:10px}.scanner-ready i{display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:#2a9a79}.scanner-panel form label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.scanner-input-wrap{height:62px;display:grid;grid-template-columns:50px 1fr auto;border:2px solid #1c6657;border-radius:9px;overflow:hidden;box-shadow:0 0 0 4px #1c66570e}.scanner-prefix{display:grid;place-items:center;color:#c58d38;background:#f3f8f6;font-size:24px}.scanner-input-wrap input{min-width:0;padding:0 8px;border:0;outline:0;font-size:20px;letter-spacing:.07em}.scanner-input-wrap button{margin:7px;padding:0 20px;border:0;border-radius:6px;color:#fff;background:#174d43;font-weight:700}.scanner-input-wrap button:disabled{opacity:.5}.catalog-hint{margin:12px 0 0;color:#7d8a85;font-size:10px}.readonly-banner{padding:24px;display:flex;align-items:flex-start;flex-direction:column;gap:8px;color:#697671}.readonly-banner strong{color:#173f37;font-size:18px}.scan-feedback{margin:14px 0;padding:14px 18px;border:1px solid;border-radius:8px;font-size:12px}.scan-feedback strong{margin-right:10px}.scan-feedback.success{border-color:#b9dacd;color:#175d4d;background:#eef8f4}.scan-feedback.unknown,.scan-feedback.ambiguous{border-color:#e8d1a8;color:#7b571c;background:#fff8e9}.scan-feedback.error{border-color:#e3bdb7;color:#8c3c31;background:#fff2f0}.activity-grid{grid-template-columns:minmax(0,1.5fr) minmax(300px,.5fr);margin-bottom:30px}.exception-panel{overflow:hidden}.exception-panel>header{padding:18px 20px;display:flex;align-items:flex-end;justify-content:space-between;border-bottom:1px solid #e8eeec}.exception-panel>header strong{display:grid;width:27px;height:27px;place-items:center;border-radius:50%;color:#79551b;background:#fff0d2;font-size:11px}.exception-empty{padding:36px 20px;color:#84908c;text-align:center}.ambiguity-card{padding:16px 18px}.ambiguity-card+.ambiguity-card{border-top:1px solid #e8eeec}.ambiguity-card p{margin:0 0 7px;font-size:12px}.ambiguity-card>span{display:block;margin-bottom:12px;color:#84908c;font-size:11px}.ambiguity-card button{width:100%;margin-top:8px;padding:11px 12px;border:1px solid #d9e3df;border-radius:7px;color:#24342f;background:#fff;text-align:left}.ambiguity-card button:hover:not(:disabled){border-color:#3d8374;background:#f4f9f7}.ambiguity-card button strong,.ambiguity-card button small{display:block}.ambiguity-card button small{margin-top:5px;color:#87928e}@media(max-width:980px){.scan-entry-grid,.activity-grid{grid-template-columns:1fr}}@media(max-width:640px){.scanner-panel{padding:20px 15px}.scanner-heading{align-items:flex-start;flex-direction:column}.scanner-input-wrap{height:auto;grid-template-columns:42px 1fr}.scanner-input-wrap input{height:56px;font-size:15px}.scanner-input-wrap button{grid-column:1/-1;height:42px;margin:0 7px 7px}}
</style>
<style scoped>
.readonly-banner button{margin-top:6px;padding:10px 16px;border:0;border-radius:7px;color:#fff;background:#174d43;font-weight:700;box-shadow:0 8px 18px #174d4324}
</style>
