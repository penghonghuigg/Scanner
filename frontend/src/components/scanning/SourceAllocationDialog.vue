<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type {
  ProductSourceAllocationState,
  RegionCatalog,
  SourceAllocationInput,
} from '../../types/scanning'

const props = defineProps<{
  state: ProductSourceAllocationState | null
  catalog: RegionCatalog
  saving: boolean
}>()
const emit = defineEmits<{
  cancel: []
  save: [items: SourceAllocationInput[]]
}>()

interface AllocationRow extends SourceAllocationInput {
  key: number
}

const rows = reactive<AllocationRow[]>([])
let nextKey = 1

watch(() => props.state, (state) => {
  rows.splice(0)
  if (!state) return
  if (state.allocations.length) {
    rows.push(...state.allocations.map((item) => ({
      key: nextKey++,
      source_type: item.source_type,
      province_name: item.province_name,
      city_name: item.city_name,
      pack_count: item.pack_count,
    })))
  } else {
    rows.push({
      key: nextKey++,
      source_type: 'UNKNOWN',
      province_name: null,
      city_name: null,
      pack_count: state.required_pack_count,
    })
  }
}, { immediate: true })

const allocatedPacks = computed(() => rows.reduce(
  (total, row) => total + (Number.isInteger(row.pack_count) ? Number(row.pack_count) : 0),
  0,
))
const quantityMatches = computed(() => (
  props.state !== null && allocatedPacks.value === props.state.required_pack_count
))

function outsideProvinces() {
  return props.catalog.provinces.filter((province) => province.name !== '安徽省')
}

function citiesFor(row: AllocationRow): string[] {
  if (row.source_type === 'ANHUI_OTHER_CITY') {
    return props.catalog.provinces
      .find((province) => province.name === '安徽省')
      ?.cities.map((city) => city.name).filter((city) => city !== '淮南市') ?? []
  }
  return props.catalog.provinces
    .find((province) => province.name === row.province_name)
    ?.cities.map((city) => city.name) ?? []
}

function changeType(row: AllocationRow): void {
  if (row.source_type === 'UNKNOWN') {
    row.province_name = null
    row.city_name = null
  } else if (row.source_type === 'LOCAL_HUAINAN') {
    row.province_name = '安徽省'
    row.city_name = '淮南市'
  } else if (row.source_type === 'ANHUI_OTHER_CITY') {
    row.province_name = '安徽省'
    row.city_name = null
  } else {
    row.province_name = null
    row.city_name = '不详'
  }
}

function changeProvince(row: AllocationRow): void {
  row.city_name = '不详'
}

function addRow(): void {
  rows.push({
    key: nextKey++,
    source_type: 'UNKNOWN',
    province_name: null,
    city_name: null,
    pack_count: 1,
  })
}

function rowValid(row: AllocationRow): boolean {
  if (!Number.isInteger(Number(row.pack_count)) || Number(row.pack_count) <= 0) return false
  if (row.source_type === 'OUTSIDE_PROVINCE') return Boolean(row.province_name)
  if (row.source_type === 'ANHUI_OTHER_CITY') return Boolean(row.city_name)
  return true
}

function save(): void {
  if (!quantityMatches.value || rows.some((row) => !rowValid(row))) return
  emit('save', rows.map((row) => ({
    source_type: row.source_type,
    province_name: row.province_name,
    city_name: row.city_name,
    pack_count: Number(row.pack_count),
  })))
}
</script>

<template>
  <div
    v-if="state"
    class="dialog-backdrop"
    data-source-dialog
    role="dialog"
    aria-modal="true"
  >
    <section class="source-dialog">
      <header>
        <div><span>SOURCE ALLOCATION</span><h3>卷烟来源地拆分</h3></div>
        <button
          type="button"
          aria-label="关闭"
          @click="emit('cancel')"
        >
          ×
        </button>
      </header>
      <p class="product-line">
        <strong>{{ state.product_snapshot.standard_name }}</strong>
        <code>{{ state.product_snapshot.carton_code }}</code>
      </p>
      <div class="allocation-summary">
        <span>应分配 <strong>{{ state.required_pack_count }}</strong> 包</span>
        <span>已填写 <strong>{{ allocatedPacks }}</strong> 包</span>
        <span :class="{ warning: !quantityMatches }">{{ quantityMatches ? '数量一致' : `相差 ${state.required_pack_count - allocatedPacks} 包` }}</span>
      </div>
      <div class="allocation-list">
        <article
          v-for="(row, index) in rows"
          :key="row.key"
        >
          <select
            v-model="row.source_type"
            :name="`source-type-${index}`"
            aria-label="来源类型"
            @change="changeType(row)"
          >
            <option
              v-for="option in catalog.source_types"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
          <select
            v-if="row.source_type === 'OUTSIDE_PROVINCE'"
            v-model="row.province_name"
            aria-label="来源省"
            @change="changeProvince(row)"
          >
            <option :value="null">
              选择省级
            </option>
            <option
              v-for="province in outsideProvinces()"
              :key="province.name"
              :value="province.name"
            >
              {{ province.name }}
            </option>
          </select>
          <select
            v-if="row.source_type === 'OUTSIDE_PROVINCE' || row.source_type === 'ANHUI_OTHER_CITY'"
            v-model="row.city_name"
            aria-label="来源市"
          >
            <option
              v-if="row.source_type === 'OUTSIDE_PROVINCE'"
              value="不详"
            >
              不详
            </option>
            <option
              v-else
              :value="null"
            >
              选择市级
            </option>
            <option
              v-for="city in citiesFor(row)"
              :key="city"
              :value="city"
            >
              {{ city }}
            </option>
          </select>
          <span
            v-if="row.source_type === 'LOCAL_HUAINAN'"
            class="fixed-location"
          >安徽省 · 淮南市</span>
          <span
            v-if="row.source_type === 'UNKNOWN'"
            class="fixed-location"
          >无需填写地区</span>
          <label><input
            v-model.number="row.pack_count"
            :name="`source-pack-count-${index}`"
            type="number"
            min="1"
            step="1"
            aria-label="包数"
          ><span>包</span></label>
          <button
            class="remove-row"
            type="button"
            :disabled="rows.length === 1"
            @click="rows.splice(index, 1)"
          >
            删除
          </button>
        </article>
      </div>
      <button
        class="add-row"
        type="button"
        @click="addRow"
      >
        + 增加来源
      </button>
      <footer>
        <button
          type="button"
          :disabled="saving"
          @click="emit('cancel')"
        >
          取消
        </button>
        <button
          class="primary"
          data-action="save-source-allocations"
          type="button"
          :disabled="saving || !quantityMatches || rows.some((row) => !rowValid(row))"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存来源拆分' }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.dialog-backdrop{position:fixed;z-index:1100;inset:0;display:grid;place-items:center;padding:20px;background:#10251f73}.source-dialog{width:min(920px,100%);max-height:calc(100vh - 40px);overflow:auto;padding:28px;border:1px solid #dbe5e1;border-radius:14px;background:#fff;box-shadow:0 26px 80px #10251f3d}.source-dialog>header{display:flex;align-items:flex-start;justify-content:space-between}.source-dialog>header span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.source-dialog h3{margin:7px 0;font-size:22px}.source-dialog>header button{border:0;color:#75827e;background:transparent;font-size:25px}.product-line{margin:14px 0;padding:14px 16px;display:flex;justify-content:space-between;border-radius:8px;background:#f4f8f6}.product-line code{color:#65736e}.allocation-summary{display:flex;gap:12px;margin-bottom:15px}.allocation-summary span{padding:7px 10px;border-radius:5px;color:#466059;background:#eef5f2;font-size:12px}.allocation-summary .warning{color:#8a5a16;background:#fff2d8}.allocation-list article{display:grid;grid-template-columns:1.15fr 1fr 1fr 110px 56px;gap:9px;align-items:center;padding:11px 0;border-bottom:1px solid #edf1ef}.allocation-list select,.allocation-list input{box-sizing:border-box;width:100%;height:38px;padding:0 9px;border:1px solid #ccd8d4;border-radius:6px;background:#fff}.allocation-list label{display:grid;grid-template-columns:1fr 24px;align-items:center}.fixed-location{color:#63716c;font-size:12px}.remove-row,.add-row,.source-dialog footer button{padding:8px 12px;border:1px solid #d1dcd8;border-radius:6px;color:#4c5b56;background:#fff;font-weight:700}.remove-row{padding-left:5px;padding-right:5px;color:#9d4439}.add-row{margin-top:15px;color:#175d4d}.source-dialog footer{margin-top:24px;display:flex;justify-content:flex-end;gap:10px}.source-dialog footer .primary{border-color:#174d43;color:#fff;background:#174d43}.source-dialog button:disabled{cursor:not-allowed;opacity:.45}@media(max-width:760px){.allocation-list article{grid-template-columns:1fr 1fr}.product-line{align-items:flex-start;flex-direction:column;gap:8px}}
</style>
