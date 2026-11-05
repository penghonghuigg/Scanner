<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { searchProductOptions } from '../../api/scanSessions'
import type { ProductOption, ScanSessionItem } from '../../types/scanning'
import { effectiveCartonCount, formatCurrency } from '../../utils/scanningPresentation'

const props = defineProps<{ open: boolean; item: ScanSessionItem | null }>()
const emit = defineEmits<{
  cancel: []
  continue: [payload: { product: ProductOption; quantity: number }]
}>()
const query = ref('')
const results = ref<ProductOption[]>([])
const selected = ref<ProductOption | null>(null)
const quantity = ref(0.1)
const searching = ref(false)
const error = ref('')

watch(() => [props.open, props.item] as const, ([open, item]) => {
  if (!open) return
  error.value = ''; results.value = []; query.value = ''
  selected.value = item ? {
    id: item.product_id,
    carton_code: item.product_snapshot.carton_code,
    brand: item.product_snapshot.brand,
    standard_name: item.product_snapshot.standard_name,
    carton_retail_price: item.product_snapshot.carton_retail_price,
    sticks_per_pack: item.product_snapshot.sticks_per_pack,
    packs_per_carton: item.product_snapshot.packs_per_carton,
  } : null
  quantity.value = item ? Math.round(effectiveCartonCount(item) * 10) / 10 : 0.1
}, { immediate: true })

const validQuantity = computed(() => {
  const value = Number(quantity.value)
  return Number.isFinite(value) && value >= 0.1 && Math.abs(value * 10 - Math.round(value * 10)) < 1e-8
})

async function search(): Promise<void> {
  const normalized = query.value.trim()
  if (!normalized || searching.value) return
  searching.value = true; error.value = ''
  try {
    const response = await searchProductOptions(normalized, 1, 20)
    results.value = response.items
    if (!response.items.length) error.value = '未找到可用卷烟品规'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '品规查询失败'
  } finally { searching.value = false }
}

function proceed(): void {
  if (!selected.value || !validQuantity.value) return
  emit('continue', { product: selected.value, quantity: Math.round(Number(quantity.value) * 10) / 10 })
}
</script>

<template>
  <div
    v-if="open"
    class="dialog-backdrop"
    data-result-item-dialog
    role="dialog"
    aria-modal="true"
  >
    <section class="result-dialog">
      <header><span>RESULT CORRECTION</span><h3>{{ item ? '修改已完成品规' : '从品规库增加卷烟' }}</h3><p>数量以 0.1 条（1 包）为最小单位，下一步填写对应来源地。</p></header>
      <form
        v-if="!item"
        class="product-search"
        @submit.prevent="search"
      >
        <label for="product-query">品规名称或条码后 6 位</label>
        <div>
          <input
            id="product-query"
            v-model="query"
            name="product-query"
            autocomplete="off"
            placeholder="例如：黄山或 129756"
          ><button
            data-action="search-products"
            type="submit"
            :disabled="searching || !query.trim()"
          >
            {{ searching ? '查询中' : '查询' }}
          </button>
        </div>
      </form>
      <div
        v-if="results.length && !item"
        class="product-options"
      >
        <button
          v-for="product in results"
          :key="product.id"
          :data-product-option="product.id"
          type="button"
          :class="{ selected: selected?.id === product.id }"
          @click="selected = product"
        >
          <strong>{{ product.standard_name }}</strong><span>{{ product.brand }} · {{ product.carton_code }} · {{ product.carton_retail_price === null ? '未维护价格' : formatCurrency(Number(product.carton_retail_price)) }}</span>
        </button>
      </div>
      <p
        v-if="error"
        class="dialog-error"
        role="alert"
      >
        {{ error }}
      </p>
      <dl
        v-if="selected"
        class="selected-product"
      >
        <div><dt>已选品规</dt><dd>{{ selected.standard_name }}</dd></div><div><dt>条形码</dt><dd><code>{{ selected.carton_code }}</code></dd></div>
      </dl>
      <label
        v-if="selected"
        class="quantity-field"
      ><span>结果数量（条）</span><input
        v-model.number="quantity"
        name="result-quantity"
        type="number"
        min="0.1"
        step="0.1"
      ><small>最少 0.1 条，只允许一位小数</small></label>
      <footer>
        <button
          type="button"
          @click="emit('cancel')"
        >
          取消
        </button><button
          class="primary"
          data-action="continue-result-item"
          type="button"
          :disabled="!selected || !validQuantity"
          @click="proceed"
        >
          下一步：填写来源地
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.dialog-backdrop{position:fixed;z-index:40;inset:0;display:grid;place-items:center;padding:24px;background:#102c2699}.result-dialog{width:min(620px,100%);max-height:90vh;overflow:auto;border-radius:14px;background:#fff;box-shadow:0 24px 70px #102c2640}.result-dialog header{padding:24px 26px 18px;border-bottom:1px solid #e4ebe8}.result-dialog header span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.result-dialog h3{margin:6px 0;color:#173f37;font-size:21px}.result-dialog header p{margin:0;color:#778580;font-size:12px}.product-search,.selected-product,.quantity-field,.dialog-error{margin:18px 26px}.product-search label,.quantity-field span{display:block;margin-bottom:7px;color:#53635d;font-size:12px;font-weight:700}.product-search>div{display:grid;grid-template-columns:1fr 76px;gap:8px}.product-search input,.quantity-field input{height:40px;padding:0 12px;border:1px solid #cfdad6;border-radius:7px}.product-search button,.primary{border:0;border-radius:7px;color:#fff;background:#174d43;font-weight:700}.product-options{margin:0 26px;display:grid;gap:8px}.product-options button{padding:12px 14px;border:1px solid #dce6e2;border-radius:8px;background:#fff;text-align:left}.product-options button.selected{border-color:#1f7563;background:#f0f8f5}.product-options strong,.product-options span{display:block}.product-options span{margin-top:4px;color:#7a8883;font-size:11px}.selected-product{padding:12px 14px;border-radius:8px;background:#f4f8f6}.selected-product div{display:flex;justify-content:space-between;gap:20px}.selected-product div+div{margin-top:8px}.selected-product dt{color:#7a8883}.selected-product dd{margin:0;color:#203c34;font-weight:700}.quantity-field{display:block}.quantity-field input{width:150px}.quantity-field small{display:block;margin-top:6px;color:#84908c}.dialog-error{color:#a23d35}.result-dialog footer{padding:16px 26px;display:flex;justify-content:flex-end;gap:10px;border-top:1px solid #e4ebe8}.result-dialog footer button{min-height:38px;padding:0 16px;border:1px solid #d5dfdb;border-radius:7px;background:#fff}.result-dialog footer .primary{border-color:#174d43;color:#fff;background:#174d43}.result-dialog button:disabled{opacity:.45}
</style>
