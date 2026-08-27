<script setup lang="ts">
/* global Blob, Event, HTMLInputElement */
import { computed, onMounted, reactive, ref } from 'vue'

import {
  buildImportIssuesCsv,
  createProduct,
  fetchImportTemplate,
  importProducts,
  listProducts,
  updateProduct,
} from '../api/products'
import type { Product, ProductImportResult, ProductInput } from '../types/catalog'

const products = ref<Product[]>([])
const total = ref(0)
const summary = reactive({ total_count: 0, active_count: 0, inactive_count: 0, ambiguous_count: 0 })
const query = ref('')
const status = ref('all')
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const importResult = ref<ProductImportResult | null>(null)
const editorOpen = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  carton_code: '',
  pack_code: '',
  brand: '',
  standard_name: '',
  carton_retail_price: '',
  sticks_per_pack: 20,
  packs_per_carton: 10,
  is_active: true,
})

const editorTitle = computed(() => editingId.value === null ? '新增品规版本' : '编辑品规版本')

async function loadProducts(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const filters: Parameters<typeof listProducts>[0] = { page: 1, page_size: 100 }
    if (query.value.trim()) filters.query = query.value.trim()
    if (status.value === 'active') filters.is_active = true
    if (status.value === 'inactive') filters.is_active = false
    if (status.value === 'ambiguous') filters.ambiguous = true
    const result = await listProducts(filters)
    products.value = result.items
    total.value = result.total
    Object.assign(summary, result.summary)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '品规加载失败'
  } finally {
    loading.value = false
  }
}

function resetForm(): void {
  Object.assign(form, {
    carton_code: '', pack_code: '', brand: '', standard_name: '', carton_retail_price: '',
    sticks_per_pack: 20, packs_per_carton: 10, is_active: true,
  })
}

function openCreate(): void {
  editingId.value = null
  resetForm()
  editorOpen.value = true
}

function openEdit(product: Product): void {
  editingId.value = product.id
  Object.assign(form, {
    carton_code: product.carton_code,
    pack_code: product.pack_code ?? '',
    brand: product.brand,
    standard_name: product.standard_name,
    carton_retail_price: product.carton_retail_price ?? '',
    sticks_per_pack: product.sticks_per_pack,
    packs_per_carton: product.packs_per_carton,
    is_active: product.is_active,
  })
  editorOpen.value = true
}

function formPayload(): ProductInput {
  return {
    carton_code: form.carton_code.trim(),
    pack_code: form.pack_code.trim() || null,
    brand: form.brand.trim(),
    standard_name: form.standard_name.trim(),
    carton_retail_price: form.carton_retail_price.trim() || null,
    sticks_per_pack: Number(form.sticks_per_pack),
    packs_per_carton: Number(form.packs_per_carton),
    is_active: form.is_active,
  }
}

async function saveProduct(): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  try {
    if (editingId.value === null) {
      await createProduct(formPayload())
      noticeMessage.value = '品规已新增'
    } else {
      await updateProduct(editingId.value, formPayload())
      noticeMessage.value = '品规已更新'
    }
    editorOpen.value = false
    await loadProducts()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function toggleProduct(product: Product): Promise<void> {
  const action = product.is_active ? '停用' : '启用'
  if (!globalThis.confirm(`确认${action}“${product.standard_name}”吗？`)) return
  try {
    await updateProduct(product.id, { is_active: !product.is_active })
    noticeMessage.value = `品规已${action}`
    await loadProducts()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : `${action}失败`
  }
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = globalThis.URL.createObjectURL(blob)
  const anchor = globalThis.document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  globalThis.URL.revokeObjectURL(url)
}

async function downloadTemplate(): Promise<void> {
  try {
    downloadBlob(await fetchImportTemplate(), '卷烟品规导入模板.xlsx')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板下载失败'
  }
}

async function handleImport(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  errorMessage.value = ''
  try {
    importResult.value = await importProducts(file)
    noticeMessage.value = '导入处理完成'
    await loadProducts()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导入失败'
  } finally {
    importing.value = false
    input.value = ''
  }
}

function downloadIssues(): void {
  if (!importResult.value?.issues.length) return
  downloadBlob(new Blob([buildImportIssuesCsv(importResult.value.issues)], { type: 'text/csv;charset=utf-8' }), '品规导入问题.csv')
}

onMounted(loadProducts)
</script>

<template>
  <div class="workspace-shell product-workspace">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="sidebar-logo">案</span><span>涉案卷烟<br><small>智能统计系统</small></span>
      </div>
      <nav aria-label="主导航">
        <RouterLink
          class="nav-item"
          to="/"
        >
          <span>⌂</span>系统首页
        </RouterLink>
        <RouterLink
          class="nav-item"
          to="/users/register"
        >
          <span>＋</span>人员注册
        </RouterLink>
        <RouterLink
          class="nav-item active"
          to="/products"
        >
          <span>▦</span>品规管理
        </RouterLink>
      </nav>
      <div class="sidebar-version">
        内部业务系统<br>Version 0.1.0
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div><p>基础数据</p><span>管理扫码识别所需的卷烟品规版本</span></div>
        <RouterLink
          class="catalog-back"
          to="/"
        >
          返回工作台
        </RouterLink>
      </header>
      <main class="catalog-page">
        <section class="catalog-hero">
          <div>
            <p class="eyebrow">
              PRODUCT CATALOG
            </p><h1>卷烟品规</h1><p>一个条码代表一个具体版本，价格和包装参数随版本独立保存。</p>
          </div>
          <div class="catalog-actions">
            <button
              data-action="template"
              type="button"
              @click="downloadTemplate"
            >
              ↓ 下载模板
            </button>
            <label
              data-action="import"
              :class="{ disabled: importing }"
            >⇧ {{ importing ? '导入中…' : '批量导入' }}<input
              type="file"
              accept=".xlsx"
              :disabled="importing"
              @change="handleImport"
            ></label>
            <button
              data-action="create"
              class="primary"
              type="button"
              @click="openCreate"
            >
              ＋ 新增品规
            </button>
          </div>
        </section>

        <p
          v-if="errorMessage"
          class="catalog-message error"
          role="alert"
        >
          {{ errorMessage }}
        </p>
        <p
          v-if="noticeMessage"
          class="catalog-message success"
        >
          {{ noticeMessage }}
        </p>

        <section
          class="catalog-stats"
          aria-label="品规统计"
        >
          <article><span>全部版本</span><strong>{{ summary.total_count }}</strong></article>
          <article><span>正在使用</span><strong>{{ summary.active_count }}</strong></article>
          <article><span>已经停用</span><strong>{{ summary.inactive_count }}</strong></article>
          <article class="warning">
            <span>歧义包码</span><strong>{{ summary.ambiguous_count }}</strong>
          </article>
        </section>

        <section
          v-if="importResult"
          class="import-summary"
        >
          <div><strong>导入结果</strong><span>新增 {{ importResult.created_count }} · 更新 {{ importResult.updated_count }} · 跳过 {{ importResult.skipped_count }} · 警告 {{ importResult.warning_count }}</span></div>
          <button
            v-if="importResult.issues.length"
            type="button"
            @click="downloadIssues"
          >
            下载问题明细
          </button>
        </section>

        <section class="catalog-panel">
          <div class="catalog-filter">
            <label><span>搜索</span><input
              v-model="query"
              placeholder="输入条码、包码、品牌或品规名称"
              @keyup.enter="loadProducts"
            ></label>
            <label><span>状态</span><select
              v-model="status"
              @change="loadProducts"
            ><option value="all">全部</option><option value="active">使用中</option><option value="inactive">已停用</option><option value="ambiguous">歧义包码</option></select></label>
            <button
              type="button"
              @click="loadProducts"
            >
              查询
            </button><small>共 {{ total }} 条</small>
          </div>
          <div class="catalog-table-wrap">
            <table>
              <thead><tr><th>识别编码</th><th>品牌 / 品规</th><th>零售价</th><th>包装规格</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-if="loading">
                  <td
                    colspan="6"
                    class="empty-cell"
                  >
                    正在加载品规…
                  </td>
                </tr>
                <tr v-else-if="products.length === 0">
                  <td
                    colspan="6"
                    class="empty-cell"
                  >
                    暂无符合条件的品规
                  </td>
                </tr>
                <tr
                  v-for="product in products"
                  v-else
                  :key="product.id"
                >
                  <td><code>{{ product.carton_code }}</code><small>包码 {{ product.pack_code || '未设置' }}</small></td>
                  <td><strong>{{ product.standard_name }}</strong><small>{{ product.brand }}</small></td>
                  <td><strong>¥ {{ product.carton_retail_price ?? '—' }} / 条</strong><small>¥ {{ product.pack_retail_price ?? '—' }} / 包</small></td>
                  <td><strong>{{ product.sticks_per_carton }} 支 / 条</strong><small>{{ product.sticks_per_pack }} 支 × {{ product.packs_per_carton }} 包</small></td>
                  <td>
                    <span :class="['state-pill', product.is_active ? 'active' : 'inactive']">{{ product.is_active ? '使用中' : '已停用' }}</span><span
                      v-if="product.is_pack_ambiguous"
                      class="ambiguity-pill"
                    >歧义包码</span>
                  </td>
                  <td>
                    <button
                      class="text-button"
                      type="button"
                      @click="openEdit(product)"
                    >
                      编辑
                    </button><button
                      class="text-button"
                      type="button"
                      @click="toggleProduct(product)"
                    >
                      {{ product.is_active ? '停用' : '启用' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>

    <div
      v-if="editorOpen"
      class="catalog-overlay"
      @click.self="editorOpen = false"
    >
      <section
        class="catalog-editor"
        role="dialog"
        aria-modal="true"
        :aria-label="editorTitle"
      >
        <header>
          <div>
            <p class="eyebrow">
              PRODUCT VERSION
            </p><h2>{{ editorTitle }}</h2>
          </div><button
            type="button"
            aria-label="关闭"
            @click="editorOpen = false"
          >
            ×
          </button>
        </header>
        <form
          data-form="product"
          @submit.prevent="saveProduct"
        >
          <label>条码（唯一）<input
            v-model="form.carton_code"
            name="carton_code"
            required
            maxlength="64"
          ></label>
          <label>包码（可不填）<input
            v-model="form.pack_code"
            name="pack_code"
            maxlength="64"
          ><small>允许重复；与任一条码冲突时不能保存。</small></label>
          <label>品牌<input
            v-model="form.brand"
            name="brand"
            required
            maxlength="100"
          ></label>
          <label>品规名称<input
            v-model="form.standard_name"
            name="standard_name"
            required
            maxlength="200"
          ></label>
          <label>条零售价（元）<input
            v-model="form.carton_retail_price"
            name="carton_retail_price"
            inputmode="decimal"
            placeholder="可不填"
          ></label>
          <div class="package-fields">
            <label>每包支数<input
              v-model.number="form.sticks_per_pack"
              name="sticks_per_pack"
              type="number"
              required
              min="1"
            ></label><label>每条包数<input
              v-model.number="form.packs_per_carton"
              name="packs_per_carton"
              type="number"
              required
              min="1"
            ></label>
          </div>
          <label class="active-check"><input
            v-model="form.is_active"
            type="checkbox"
          > 保存后立即启用</label>
          <footer>
            <button
              type="button"
              @click="editorOpen = false"
            >
              取消
            </button><button
              class="primary"
              type="submit"
              :disabled="saving"
            >
              {{ saving ? '保存中…' : '保存品规' }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </div>
</template>

<style src="../styles/catalog.css"></style>
