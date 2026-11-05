<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  IntegrationSnapshot,
  ProductSourceAllocationState,
  ScanSessionStatus,
} from '../../types/scanning'

const props = defineProps<{
  status: ScanSessionStatus
  canWrite: boolean
  sourceStates: ProductSourceAllocationState[]
  unknownCount: number
  ambiguityCount: number
  completing: boolean
  downloading: boolean
  importing: boolean
  integrationSnapshot: IntegrationSnapshot | null
}>()
const emit = defineEmits<{
  complete: [confirmExceptions: boolean]
  download: []
  importJiandaoyun: []
}>()

const showDialog = ref(false)
const showIntegrationDialog = ref(false)
const confirmExceptions = ref(false)
const incompleteCount = computed(() => props.sourceStates.filter(
  (item) => item.required_pack_count !== item.allocated_pack_count,
).length)
const exceptionCount = computed(() => props.unknownCount + props.ambiguityCount)

watch(() => props.status, (status) => {
  if (status === 'COMPLETED') showDialog.value = false
})

watch(() => props.integrationSnapshot?.status, (status) => {
  if (status === 'SUCCEEDED') showIntegrationDialog.value = false
})

const integrationLabel = computed(() => {
  if (props.importing || props.integrationSnapshot?.status === 'PENDING') return '正在导入…'
  if (props.integrationSnapshot?.status === 'SUCCEEDED') return '已导入'
  if (props.integrationSnapshot?.status === 'FAILED') return '重新导入'
  if (props.integrationSnapshot?.status === 'UNCERTAIN') return '导入结果待核查'
  return '一键导入简道云'
})
const integrationDisabled = computed(() => props.importing || [
  'PENDING', 'SUCCEEDED', 'UNCERTAIN',
].includes(props.integrationSnapshot?.status ?? ''))
const integrationTitle = computed(() => {
  if (props.integrationSnapshot?.status === 'SUCCEEDED') {
    return '该盘点批次已经导入简道云，不能重复导入。'
  }
  if (props.integrationSnapshot?.status === 'UNCERTAIN') {
    return '导入结果不确定，请按标识 ID 到简道云人工核查。'
  }
  return ''
})

function openCompletion(): void {
  confirmExceptions.value = false
  showDialog.value = true
}

function complete(): void {
  if (exceptionCount.value > 0 && !confirmExceptions.value) return
  emit('complete', confirmExceptions.value)
}

function openIntegrationConfirmation(): void {
  if (integrationDisabled.value) return
  showIntegrationDialog.value = true
}

function confirmIntegration(): void {
  showIntegrationDialog.value = false
  emit('importJiandaoyun')
}
</script>

<template>
  <section class="completion-panel">
    <div>
      <span>FINAL REVIEW</span>
      <h2>{{ status === 'COMPLETED' ? '批次已完成' : '核对与完成批次' }}</h2>
      <p v-if="status === 'DRAFT'">
        已完成来源拆分 {{ sourceStates.length - incompleteCount }} / {{ sourceStates.length }} 个品规；完成后扫码、数量和来源均转为只读。
      </p>
      <p v-else>
        数据已封存，可随时重新生成并下载 Excel，服务器不保存导出文件。
      </p>
    </div>
    <div class="completion-actions">
      <button
        v-if="status === 'DRAFT' && canWrite"
        data-action="complete-session"
        type="button"
        :disabled="completing || !sourceStates.length || incompleteCount > 0"
        @click="openCompletion"
      >
        {{ incompleteCount > 0 ? `还有 ${incompleteCount} 个品规未分配来源` : '完成批次' }}
      </button>
      <button
        v-if="status === 'COMPLETED'"
        class="download"
        data-action="download-excel"
        type="button"
        :disabled="downloading"
        @click="emit('download')"
      >
        {{ downloading ? '生成中…' : '导出 Excel' }}
      </button>
      <button
        v-if="status === 'COMPLETED' && canWrite"
        class="integration"
        data-action="import-jiandaoyun"
        type="button"
        :disabled="integrationDisabled"
        :title="integrationTitle"
        @click="openIntegrationConfirmation"
      >
        {{ integrationLabel }}
      </button>
    </div>
    <p
      v-if="status === 'COMPLETED' && integrationSnapshot?.status === 'FAILED'"
      class="integration-note failed"
    >
      {{ integrationSnapshot.last_error_message || '上次导入失败，可以复用原快照重新导入。' }}
    </p>
    <p
      v-if="status === 'COMPLETED' && integrationSnapshot?.status === 'UNCERTAIN'"
      class="integration-note uncertain"
    >
      请按标识 ID 到简道云人工核查，确认前不要再次导入。
    </p>
  </section>

  <div
    v-if="showDialog"
    class="dialog-backdrop"
    data-completion-dialog
    role="dialog"
    aria-modal="true"
  >
    <section class="completion-dialog">
      <span>FINAL CONFIRMATION</span>
      <h3>确认完成并封存批次？</h3>
      <p>完成后不能继续扫码、调整数量或修改来源地。</p>
      <dl>
        <div><dt>品规来源</dt><dd>{{ sourceStates.length }} / {{ sourceStates.length }} 已核对</dd></div>
        <div><dt>未识别编码</dt><dd>{{ unknownCount }} 次</dd></div>
        <div><dt>未解决歧义</dt><dd>{{ ambiguityCount }} 次</dd></div>
      </dl>
      <label class="exception-confirm">
        <input
          v-model="confirmExceptions"
          name="confirm-exceptions"
          type="checkbox"
          :disabled="exceptionCount === 0"
        >
        <span>我已核对异常编码，确认其不计入卷烟数量并随 Excel 导出</span>
      </label>
      <footer>
        <button
          type="button"
          :disabled="completing"
          @click="showDialog = false"
        >
          返回核对
        </button>
        <button
          class="primary"
          data-action="confirm-completion"
          type="button"
          :disabled="completing || (exceptionCount > 0 && !confirmExceptions)"
          @click="complete"
        >
          {{ completing ? '正在完成…' : '确认完成批次' }}
        </button>
      </footer>
    </section>
  </div>

  <div
    v-if="showIntegrationDialog"
    class="dialog-backdrop"
    data-integration-dialog
    role="dialog"
    aria-modal="true"
  >
    <section class="completion-dialog integration-dialog">
      <span>EXTERNAL REGISTRATION</span>
      <h3>确认导入简道云？</h3>
      <p>系统将按当前盘点结果生成不可变快照，并在简道云创建一条登记数据。</p>
      <div class="integration-warning">
        提交成功后不能重复导入；网络中断或结果不确定时需要人工核查。
      </div>
      <footer>
        <button
          type="button"
          @click="showIntegrationDialog = false"
        >
          取消
        </button>
        <button
          class="primary"
          data-action="confirm-jiandaoyun-import"
          type="button"
          :disabled="importing"
          @click="confirmIntegration"
        >
          确认导入
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.completion-panel{position:relative;margin-top:16px;padding:20px 22px;display:flex;align-items:center;justify-content:space-between;gap:24px;border:1px solid #dfe7e4;border-left:4px solid #c7923e;background:#fff}.completion-panel>div>span,.completion-dialog>span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.completion-panel h2{margin:5px 0;color:#1d312b;font-size:18px}.completion-panel p{margin:0;color:#75827d;font-size:12px}.completion-actions{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.completion-actions button{min-width:150px;padding:11px 16px;border:1px solid #174d43;border-radius:7px;color:#fff;background:#174d43;font-weight:800}.completion-actions button.download{border-color:#b98536;background:#b98536}.completion-actions button.integration{border-color:#236b5e;background:#236b5e}.completion-actions button:disabled{cursor:not-allowed;opacity:.55}.completion-panel .integration-note{position:absolute;right:22px;bottom:4px;color:#8a5d18;font-size:10px}.completion-panel .integration-note.uncertain{color:#9b3d34}.dialog-backdrop{position:fixed;z-index:1100;inset:0;display:grid;place-items:center;padding:20px;background:#10251f73}.completion-dialog{width:min(520px,100%);padding:30px;border-radius:14px;background:#fff;box-shadow:0 26px 80px #10251f3d}.completion-dialog h3{margin:8px 0;font-size:22px}.completion-dialog>p{margin:0 0 18px;color:#7b8783;font-size:13px}.completion-dialog dl{margin:0;padding:14px 16px;border-radius:8px;background:#f5f8f7}.completion-dialog dl div{display:flex;justify-content:space-between;padding:6px 0}.completion-dialog dt{color:#687670}.completion-dialog dd{margin:0;font-weight:800}.exception-confirm,.integration-warning{margin-top:16px;padding:13px;border:1px solid #ead2a7;border-radius:7px;color:#76531c;background:#fff8ea;font-size:12px;line-height:1.5}.exception-confirm{display:flex;align-items:flex-start;gap:9px}.completion-dialog footer{margin-top:22px;display:flex;justify-content:flex-end;gap:10px}.completion-dialog footer button{padding:10px 17px;border:1px solid #d1dcd8;border-radius:7px;color:#45554f;background:#fff;font-weight:700}.completion-dialog footer .primary{border-color:#174d43;color:#fff;background:#174d43}.completion-dialog button:disabled{cursor:not-allowed;opacity:.5}@media(max-width:640px){.completion-panel{align-items:flex-start;flex-direction:column}.completion-actions,.completion-actions button{width:100%}.completion-panel .integration-note{position:static}}
</style>
