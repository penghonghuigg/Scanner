<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import type { ScanSessionItem } from '../../types/scanning'
import { effectiveCartonCount, formatCurrency, referenceAmount } from '../../utils/scanningPresentation'

const props = defineProps<{
  items: ScanSessionItem[]
  canWrite: boolean
  completed?: boolean
  adjustingProductId: number | null
  removingProductId: number | null
}>()
const emit = defineEmits<{
  adjust: [payload: { productId: number; operation: 'DELTA' | 'SET'; quantity: number }]
  allocate: [item: ScanSessionItem]
  remove: [item: ScanSessionItem]
  edit: [item: ScanSessionItem]
}>()
const quantities = reactive<Record<number, number>>({})
const pendingRemoval = ref<ScanSessionItem | null>(null)

watch(
  () => props.items,
  (items) => {
    for (const item of items) {
      quantities[item.product_id] = Math.round(effectiveCartonCount(item) * 10) / 10
    }
  },
  { immediate: true, deep: true },
)

function setQuantity(productId: number): void {
  const quantity = Number(quantities[productId])
  const tenths = Math.round(quantity * 10)
  if (
    !Number.isFinite(quantity)
    || quantity < 0
    || Math.abs(quantity * 10 - tenths) > Number.EPSILON * 10
  ) return
  emit('adjust', { productId, operation: 'SET', quantity: tenths / 10 })
}

function requestRemoval(item: ScanSessionItem): void {
  if (!props.canWrite || props.removingProductId !== null) return
  pendingRemoval.value = item
}

function confirmRemoval(): void {
  if (!pendingRemoval.value) return
  const item = pendingRemoval.value
  pendingRemoval.value = null
  emit('remove', item)
}

function barcodePrefix(code: string): string {
  return code.length > 6 ? code.slice(0, -6) : ''
}

function barcodeSuffix(code: string): string {
  return code.slice(-6)
}
</script>

<template>
  <section class="quantity-panel">
    <header>
      <div>
        <span>INVENTORY BY PRODUCT</span>
        <h2>品规数量统计</h2>
        <p>相同条码品规自动累计；同名称不同条码平级显示。</p>
      </div>
    </header>

    <div
      v-if="!items.length"
      class="table-empty"
    >
      尚未识别卷烟，请先扫描条码或包码。
    </div>
    <div
      v-else
      class="product-table-scroll"
    >
      <table class="product-table">
        <colgroup>
          <col class="col-sequence"><col class="col-brand"><col class="col-name">
          <col class="col-code"><col class="col-type"><col class="col-ratio">
          <col class="col-price"><col class="col-quantity"><col class="col-subtotal">
          <col class="col-operation">
        </colgroup>
        <thead>
          <tr>
            <th>序号</th><th>品牌</th><th>卷烟名称（标准品规）</th><th>已扫描条码</th>
            <th>类型</th><th>条支比</th><th>零售价</th><th>数量（条）</th>
            <th>金额小计</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, index) in items"
            :key="item.product_id"
            data-product-row
          >
            <td class="sequence">
              {{ index + 1 }}
            </td>
            <td><strong class="brand">{{ item.product_snapshot.brand }}</strong></td>
            <td><strong class="product-name">{{ item.product_snapshot.standard_name }}</strong></td>
            <td>
              <code class="barcode"><span>{{ barcodePrefix(item.product_snapshot.carton_code) }}</span><span class="barcode-suffix">{{ barcodeSuffix(item.product_snapshot.carton_code) }}</span></code>
            </td>
            <td>卷烟</td>
            <td>{{ item.product_snapshot.sticks_per_carton }}</td>
            <td>
              <strong class="price">
                {{ item.product_snapshot.carton_retail_price === null ? '未维护' : formatCurrency(Number(item.product_snapshot.carton_retail_price)) }}
              </strong>
            </td>
            <td>
              <div
                v-if="completed"
                class="completed-quantity"
              >
                <strong>{{ effectiveCartonCount(item).toFixed(1) }}</strong>
                <button
                  :data-action="`edit-result-${item.product_id}`"
                  type="button"
                  :disabled="!canWrite"
                  @click="emit('edit', item)"
                >
                  修改
                </button>
              </div>
              <div
                v-else
                class="quantity-control"
              >
                <button
                  :data-action="`decrement-${item.product_id}`"
                  type="button"
                  aria-label="减少 0.1 条"
                  :disabled="!canWrite || adjustingProductId !== null || removingProductId === item.product_id || effectiveCartonCount(item) <= 0"
                  @click="emit('adjust', { productId: item.product_id, operation: 'DELTA', quantity: -0.1 })"
                >
                  −
                </button>
                <input
                  v-model.number="quantities[item.product_id]"
                  :name="`carton-quantity-${item.product_id}`"
                  type="number"
                  min="0"
                  step="0.1"
                  :aria-label="`${item.product_snapshot.standard_name}数量（条）`"
                  :disabled="!canWrite || adjustingProductId === item.product_id || removingProductId === item.product_id"
                  @keydown.enter.prevent="setQuantity(item.product_id)"
                >
                <button
                  :data-action="`increment-${item.product_id}`"
                  type="button"
                  aria-label="增加 0.1 条"
                  :disabled="!canWrite || adjustingProductId !== null || removingProductId === item.product_id"
                  @click="emit('adjust', { productId: item.product_id, operation: 'DELTA', quantity: 0.1 })"
                >
                  +
                </button>
                <button
                  class="save"
                  :data-action="`set-${item.product_id}`"
                  type="button"
                  :disabled="!canWrite || adjustingProductId !== null || removingProductId === item.product_id"
                  @click="setQuantity(item.product_id)"
                >
                  确认
                </button>
              </div>
            </td>
            <td>
              <strong class="subtotal">
                {{ referenceAmount(item) === null ? '—' : formatCurrency(referenceAmount(item) ?? 0) }}
              </strong>
            </td>
            <td>
              <div class="row-actions">
                <button
                  class="source-button"
                  :data-action="`allocate-source-${item.product_id}`"
                  type="button"
                  :disabled="!canWrite || adjustingProductId !== null || removingProductId !== null"
                  @click="emit('allocate', item)"
                >
                  来源拆分
                </button>
                <button
                  class="remove-button"
                  :data-action="`delete-${item.product_id}`"
                  type="button"
                  :disabled="!canWrite || adjustingProductId !== null || removingProductId !== null"
                  @click="requestRemoval(item)"
                >
                  {{ removingProductId === item.product_id ? '删除中' : '删除' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="pendingRemoval"
      class="dialog-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="remove-dialog-title"
    >
      <section class="remove-dialog">
        <span class="dialog-mark">!</span>
        <h3 id="remove-dialog-title">
          确认移除该品规统计？
        </h3>
        <p>将从当前批次统计中移除，不会删除历史扫码流水。</p>
        <dl>
          <div><dt>卷烟品规</dt><dd>{{ pendingRemoval.product_snapshot.standard_name }}</dd></div>
          <div><dt>卷烟条码</dt><dd><code>{{ pendingRemoval.product_snapshot.carton_code }}</code></dd></div>
        </dl>
        <footer>
          <button
            data-action="cancel-remove"
            type="button"
            @click="pendingRemoval = null"
          >
            取消
          </button>
          <button
            class="danger"
            data-action="confirm-remove"
            type="button"
            @click="confirmRemoval"
          >
            确认删除
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>

<style scoped>
.quantity-panel{overflow:hidden;border:1px solid #dfe7e4;background:#fff}.quantity-panel>header{padding:20px 22px;border-bottom:1px solid #e8eeec}.quantity-panel header span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.quantity-panel h2{margin:5px 0;color:#1d312b;font-size:19px}.quantity-panel header p{margin:0;color:#82908b;font-size:11px}.table-empty{padding:42px 20px;color:#84908c;text-align:center}.product-table-scroll{overflow:visible}.product-table{width:100%;border-collapse:collapse;table-layout:fixed;color:#31443e}.product-table th,.product-table td{padding:14px 6px;border-bottom:1px solid #e8eeec;text-align:center;vertical-align:middle}.product-table th{padding-top:12px;padding-bottom:12px;color:#6f7f79;background:#f4f8f6;font-size:13px;font-weight:700}.product-table td{font-size:14px}.product-table tbody tr:last-child td{border-bottom:0}.col-sequence{width:4%}.col-brand{width:7%}.col-name{width:15%}.col-code{width:14%}.col-type{width:5%}.col-ratio{width:6%}.col-price{width:9%}.col-quantity{width:20%}.col-subtotal{width:10%}.col-operation{width:10%}.sequence{color:#8a9591}.brand{font-weight:700}.product-name{display:-webkit-box;overflow:hidden;color:#173f37;font-size:15px;font-weight:800;line-height:1.4;-webkit-box-orient:vertical;-webkit-line-clamp:2}.product-table code{color:#53635d;background:transparent;font-family:Consolas,"Courier New",monospace;font-size:13px}.barcode{white-space:nowrap}.barcode-suffix{color:#c23934;font-weight:800}.price,.subtotal{color:#8b611f;font-variant-numeric:tabular-nums}.quantity-control{display:flex;align-items:center;justify-content:center;gap:5px}.quantity-control button{width:30px;height:32px;border:1px solid #cfdad6;border-radius:5px;color:#174d43;background:#fff;font-weight:800}.quantity-control input{width:60px;height:32px;border:1px solid #cfdad6;border-radius:5px;text-align:center;font-size:14px}.quantity-control .save{width:48px;color:#fff;background:#174d43;font-size:11px}.quantity-control button:disabled,.quantity-control input:disabled,.row-actions button:disabled{cursor:not-allowed;opacity:.45}.quantity-control button:focus-visible,.quantity-control input:focus-visible,.row-actions button:focus-visible{outline:2px solid #c58d38;outline-offset:2px}.row-actions{display:flex;align-items:center;flex-direction:column;gap:6px}.row-actions button{min-width:66px;padding:6px 8px;border-radius:6px;font-size:12px;font-weight:700}.source-button{border:1px solid #9fc4b8;color:#175d4d;background:#eff8f5}.remove-button{border:1px solid #d89b92;color:#a33b30;background:#fff5f3}.remove-button:hover:not(:disabled){border-color:#b9493c;background:#ffebe7}.dialog-backdrop{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:20px;background:#10251f73}.remove-dialog{width:min(440px,100%);padding:28px;border:1px solid #e7d4cf;border-radius:12px;background:#fff;box-shadow:0 24px 70px #10251f38;text-align:center}.dialog-mark{display:grid!important;width:42px;height:42px;margin:0 auto 14px;place-items:center;border-radius:50%;color:#a33b30!important;background:#fff0ed;font-size:23px!important;letter-spacing:0!important}.remove-dialog h3{margin:0;color:#203b33;font-size:20px}.remove-dialog>p{margin:10px 0 18px;color:#74817d;font-size:13px}.remove-dialog dl{margin:0;padding:14px 16px;border-radius:8px;background:#f7f9f8;text-align:left}.remove-dialog dl div{display:grid;grid-template-columns:80px 1fr;gap:12px}.remove-dialog dl div+div{margin-top:9px}.remove-dialog dt{color:#7b8984;font-size:12px}.remove-dialog dd{margin:0;color:#263d36;font-size:13px;font-weight:700}.remove-dialog footer{margin-top:22px;display:flex;justify-content:flex-end;gap:10px}.remove-dialog footer button{min-width:90px;padding:9px 16px;border:1px solid #d6dfdc;border-radius:6px;color:#40514c;background:#fff;font-weight:700}.remove-dialog footer .danger{border-color:#b9493c;color:#fff;background:#b9493c}@media(max-width:640px){.quantity-panel>header{padding:18px 15px}.product-table th,.product-table td{padding-left:4px;padding-right:4px}}
.completed-quantity{display:flex;align-items:center;justify-content:center;gap:7px}.completed-quantity strong{font-variant-numeric:tabular-nums}.completed-quantity button{padding:6px 9px;border:1px solid #bfd1ca;border-radius:5px;color:#174d43;background:#f4f9f7}.completed-quantity button:disabled{opacity:.45}
</style>
