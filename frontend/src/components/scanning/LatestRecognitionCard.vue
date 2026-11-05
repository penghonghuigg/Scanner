<script setup lang="ts">
import type { ScanEvent } from '../../types/scanning'
import { formatChinaDateTime, formatCurrency } from '../../utils/scanningPresentation'

defineProps<{ event: ScanEvent | null }>()
</script>

<template>
  <article
    class="latest-card"
    data-latest-recognition
  >
    <header>
      <div><span>LATEST MATCH</span><h2>最近识别</h2></div>
      <time v-if="event">{{ formatChinaDateTime(event.created_at) }}</time>
      <time v-else>暂无记录</time>
    </header>
    <div
      v-if="event?.product_snapshot"
      class="recognition-body"
    >
      <h3>{{ event.product_snapshot.standard_name }}</h3>
      <dl>
        <div><dt>品牌</dt><dd>{{ event.product_snapshot.brand }}</dd></div>
        <div><dt>卷烟类型</dt><dd>卷烟</dd></div>
        <div>
          <dt>卷烟条码</dt><dd class="code">
            {{ event.product_snapshot.carton_code }}
          </dd>
        </div>
        <div><dt>条码后 6 位</dt><dd>{{ event.product_snapshot.carton_code.slice(-6) }}</dd></div>
        <div><dt>条支比</dt><dd>{{ event.product_snapshot.sticks_per_carton }} 支/条</dd></div>
        <div>
          <dt>零售价({{ event.product_snapshot.sticks_per_carton }}支)</dt><dd class="price">
            {{ event.product_snapshot.carton_retail_price === null ? '未维护价格' : formatCurrency(Number(event.product_snapshot.carton_retail_price)) }}
          </dd>
        </div>
      </dl>
    </div>
    <div
      v-else
      class="recognition-empty"
    >
      <strong>等待扫码……</strong>
      <p>扫描成功后，这里将显示品规、条码及价格信息。</p>
    </div>
  </article>
</template>

<style scoped>
.latest-card{height:100%;overflow:hidden;border:1px solid #dfe7e4;background:#fff}.latest-card header{padding:18px 20px;display:flex;align-items:flex-end;justify-content:space-between;border-bottom:1px solid #e8eeec}.latest-card header span{color:#9a7131;font-size:9px;font-weight:800;letter-spacing:.18em}.latest-card h2{margin:5px 0 0;color:#1e312c;font-size:18px}.latest-card time{color:#75827e;font-size:11px;font-variant-numeric:tabular-nums}.recognition-body{padding:20px}.recognition-body h3{margin:0 0 16px;color:#173f37;font-size:21px}.recognition-body dl{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:12px 20px}.recognition-body dl div{min-width:0}.recognition-body dt{color:#8a9591;font-size:10px}.recognition-body dd{margin:4px 0 0;color:#273a34;font-size:12px;font-weight:700}.recognition-body .code{font-family:Consolas,monospace;letter-spacing:.04em}.recognition-body .price{color:#9a6a20}.recognition-empty{padding:38px 20px;color:#83908b;text-align:center}.recognition-empty strong{color:#53625d}.recognition-empty p{margin:9px 0 0;font-size:11px}@media(max-width:520px){.recognition-body dl{grid-template-columns:1fr}}
</style>
