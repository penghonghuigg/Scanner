<script setup lang="ts">
import { computed } from 'vue'

import type { ScanSessionItem } from '../../types/scanning'
import {
  equivalentCartonCount,
  formatCurrency,
  groupInventoryItems,
  referenceAmount,
} from '../../utils/scanningPresentation'

const props = defineProps<{
  items: ScanSessionItem[]
  unknownCount: number
}>()

const totalCartons = computed(() => (
  props.items.reduce((total, item) => total + equivalentCartonCount(item), 0)
))
const productCount = computed(() => groupInventoryItems(props.items).length)
const totalAmount = computed(() => (
  props.items.reduce((total, item) => total + (referenceAmount(item) ?? 0), 0)
))

function quantityText(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}
</script>

<template>
  <section
    class="inventory-metrics"
    aria-label="盘点汇总"
  >
    <article>
      <span>累计扫描数量</span>
      <strong>{{ quantityText(totalCartons) }}<small>条</small></strong>
      <p>包含人工调整和包码折算数量</p>
    </article>
    <article>
      <span>已盘品规</span>
      <strong>{{ productCount }}<small>种</small></strong>
      <p>按标准卷烟名称合并</p>
    </article>
    <article>
      <span>参考零售价合计</span>
      <strong>{{ formatCurrency(totalAmount) }}</strong>
      <p>折合条数 × 数据库条零售价</p>
    </article>
    <article>
      <span>未识别条码</span>
      <strong>{{ unknownCount }}<small>次</small></strong>
      <p>可在扫码流水中追溯</p>
    </article>
  </section>
</template>

<style scoped>
.inventory-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid #dfe7e4;border-top:0;background:#fff}.inventory-metrics article{position:relative;padding:20px 22px}.inventory-metrics article+article{border-left:1px solid #e8eeec}.inventory-metrics article::before{position:absolute;top:0;left:22px;width:34px;height:3px;background:#c58d38;content:""}.inventory-metrics span{display:block;color:#6e7c77;font-size:12px}.inventory-metrics strong{display:block;margin-top:10px;color:#173f37;font-size:26px;line-height:1.1;font-variant-numeric:tabular-nums}.inventory-metrics small{margin-left:5px;color:#65736e;font-size:12px}.inventory-metrics p{margin:8px 0 0;color:#929c98;font-size:10px}@media(max-width:900px){.inventory-metrics{grid-template-columns:1fr 1fr}.inventory-metrics article:nth-child(3){border-left:0}.inventory-metrics article:nth-child(n+3){border-top:1px solid #e8eeec}}@media(max-width:520px){.inventory-metrics{grid-template-columns:1fr}.inventory-metrics article+article{border-left:0;border-top:1px solid #e8eeec}}
</style>
