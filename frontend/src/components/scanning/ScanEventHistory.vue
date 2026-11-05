<script setup lang="ts">
import type { ScanEventPage } from '../../types/scanning'
import { formatChinaDateTime } from '../../utils/scanningPresentation'

defineProps<{ page: ScanEventPage; loading: boolean }>()
const emit = defineEmits<{ 'page-change': [page: number] }>()

function eventName(eventType: string, result: string): string {
  if (eventType === 'ADJUST') return '人工调整'
  if (eventType === 'RESOLVE') return '歧义已解决'
  if (result === 'SUCCESS') return '识别成功'
  if (result === 'UNKNOWN') return '未识别'
  return '待处理歧义'
}
</script>

<template>
  <section class="history-panel">
    <header><div><span>TRACEABLE EVENTS</span><h2>最近流水</h2></div><strong>共 {{ page.total }} 条</strong></header>
    <div
      v-if="loading"
      class="history-empty"
    >
      正在加载流水……
    </div>
    <div
      v-else-if="!page.items.length"
      class="history-empty"
    >
      暂无记录
    </div>
    <div
      v-else
      class="history-list"
    >
      <article
        v-for="event in page.items"
        :key="event.id"
        data-scan-event
      >
        <span :class="['event-badge', event.event_type.toLowerCase(), event.result.toLowerCase()]">{{ eventName(event.event_type, event.result) }}</span>
        <div><strong>{{ event.product_snapshot?.standard_name ?? event.raw_code }}</strong><small>{{ event.reason ?? `${event.raw_code} · ${event.operator_name}` }}</small></div>
        <time>{{ formatChinaDateTime(event.created_at) }}</time>
      </article>
    </div>
    <footer>
      <button
        type="button"
        :disabled="loading || page.page <= 1"
        @click="emit('page-change', page.page - 1)"
      >
        上一页
      </button>
      <span>第 {{ page.page }} / {{ Math.max(1, Math.ceil(page.total / page.page_size)) }} 页</span>
      <button
        data-action="next-events"
        type="button"
        :disabled="loading || page.page * page.page_size >= page.total"
        @click="emit('page-change', page.page + 1)"
      >
        下一页
      </button>
    </footer>
  </section>
</template>

<style scoped>
.history-panel{overflow:hidden;border:1px solid #dfe7e4;background:#fff}.history-panel header{padding:18px 20px;display:flex;align-items:flex-end;justify-content:space-between;border-bottom:1px solid #e8eeec}.history-panel header span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.history-panel h2{margin:5px 0 0;color:#1d312b;font-size:18px}.history-panel header strong{color:#71807b;font-size:11px}.history-empty{padding:36px 20px;color:#84908c;text-align:center}.history-list article{padding:13px 18px;display:grid;grid-template-columns:82px 1fr auto;gap:12px;align-items:center}.history-list article+article{border-top:1px solid #edf1ef}.event-badge{padding:5px 7px;border-radius:5px;color:#17614f;background:#eaf6f1;text-align:center;font-size:10px}.event-badge.unknown{color:#8b5d17;background:#fff3dc}.event-badge.ambiguous{color:#8a4e26;background:#fff0e4}.event-badge.adjust{color:#72501b;background:#fff1d5}.history-list strong,.history-list small{display:block}.history-list small{margin-top:4px;color:#88938f;font-size:10px}.history-list time{color:#778580;font-size:10px;font-variant-numeric:tabular-nums}.history-panel footer{padding:13px 18px;display:flex;align-items:center;justify-content:flex-end;gap:12px;border-top:1px solid #e8eeec;background:#fafbfb}.history-panel footer button{padding:7px 11px;border:1px solid #d4dfdb;border-radius:5px;color:#23443b;background:#fff}.history-panel footer button:disabled{opacity:.4}.history-panel footer span{color:#778580;font-size:10px}@media(max-width:640px){.history-list article{grid-template-columns:75px 1fr}.history-list time{grid-column:2}.history-panel footer{justify-content:center}}
</style>
