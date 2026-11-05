<script setup lang="ts">
import { ref, watch } from 'vue'

import type { AdjustmentReasonType, ScanSessionItem } from '../../types/scanning'

const props = defineProps<{
  item: ScanSessionItem | null
  operation: 'DELTA' | 'SET'
  quantity: number
  submitting: boolean
}>()
const emit = defineEmits<{
  cancel: []
  confirm: [payload: { reasonType: AdjustmentReasonType; reasonNote: string }]
}>()

const reasonType = ref<AdjustmentReasonType>('ONSITE_VERIFICATION')
const reasonNote = ref('')

watch(() => props.item, () => {
  reasonType.value = 'ONSITE_VERIFICATION'
  reasonNote.value = ''
})

const reasons: Array<{ value: AdjustmentReasonType; label: string }> = [
  { value: 'ONSITE_VERIFICATION', label: '现场核对修正' },
  { value: 'SCAN_CORRECTION', label: '扫码录入纠错' },
  { value: 'LOOSE_PACK_VERIFICATION', label: '散包数量核对' },
  { value: 'OTHER', label: '其他原因' },
]

function confirm(): void {
  if (reasonType.value === 'OTHER' && !reasonNote.value.trim()) return
  emit('confirm', { reasonType: reasonType.value, reasonNote: reasonNote.value.trim() })
}
</script>

<template>
  <div
    v-if="item"
    class="dialog-backdrop"
    data-adjustment-dialog
    role="dialog"
    aria-modal="true"
  >
    <section class="form-dialog">
      <header>
        <span>QUANTITY REVIEW</span>
        <h3>确认数量调整</h3>
        <p>{{ item.product_snapshot.standard_name }} · {{ operation === 'DELTA' ? '增减' : '设为' }} {{ quantity }} 条</p>
      </header>
      <label>
        <span>调整原因</span>
        <select
          v-model="reasonType"
          name="adjustment-reason"
        >
          <option
            v-for="reason in reasons"
            :key="reason.value"
            :value="reason.value"
          >
            {{ reason.label }}
          </option>
        </select>
      </label>
      <label v-if="reasonType === 'OTHER'">
        <span>具体说明</span>
        <textarea
          v-model="reasonNote"
          name="adjustment-reason-note"
          maxlength="200"
          placeholder="请填写本次调整原因"
        />
      </label>
      <footer>
        <button
          type="button"
          :disabled="submitting"
          @click="emit('cancel')"
        >
          取消
        </button>
        <button
          class="primary"
          data-action="confirm-adjustment"
          type="button"
          :disabled="submitting || (reasonType === 'OTHER' && !reasonNote.trim())"
          @click="confirm"
        >
          {{ submitting ? '提交中…' : '确认调整' }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.dialog-backdrop{position:fixed;z-index:1100;inset:0;display:grid;place-items:center;padding:20px;background:#10251f73}.form-dialog{width:min(480px,100%);padding:28px;border:1px solid #dbe5e1;border-radius:14px;background:#fff;box-shadow:0 26px 80px #10251f3d}.form-dialog header>span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.form-dialog h3{margin:7px 0;color:#173f37;font-size:21px}.form-dialog header p{margin:0 0 22px;color:#77847f;font-size:13px}.form-dialog label{display:block;margin-top:14px}.form-dialog label>span{display:block;margin-bottom:7px;color:#50615b;font-size:12px;font-weight:700}.form-dialog select,.form-dialog textarea{box-sizing:border-box;width:100%;padding:11px 12px;border:1px solid #ccd8d4;border-radius:7px;color:#263b35;background:#fff;font:inherit}.form-dialog textarea{min-height:82px;resize:vertical}.form-dialog footer{margin-top:24px;display:flex;justify-content:flex-end;gap:10px}.form-dialog button{padding:10px 18px;border:1px solid #d1dcd8;border-radius:7px;color:#45554f;background:#fff;font-weight:700}.form-dialog button.primary{border-color:#174d43;color:#fff;background:#174d43}.form-dialog button:disabled{cursor:not-allowed;opacity:.5}
</style>
