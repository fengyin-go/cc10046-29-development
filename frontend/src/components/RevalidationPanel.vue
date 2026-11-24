<template>
  <article class="panel" data-testid="revalidation-entry">
    <header class="panel-head">
      <div>
        <h3>字段复验批次</h3>
        <p class="panel-desc">
          校验规则不只逐条提交：把多个来源的规则行编成一组复验，逐条记录受影响列与上游依赖。
        </p>
      </div>
      <RouterLink class="btn primary" to="/field_revalidation" data-testid="open-revalidation">
        进入字段复验
      </RouterLink>
    </header>
    <table class="data-table">
      <thead>
        <tr>
          <th>批次标识</th>
          <th>状态</th>
          <th>来源</th>
          <th>待补</th>
          <th>已通过</th>
          <th>未受影响</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in batches" :key="item.批次标识">
          <td>{{ item.批次标识 }}</td>
          <td>{{ item.状态 }}</td>
          <td>{{ item.来源.join('、') }}</td>
          <td>{{ item.状态统计['待补'] ?? 0 }}</td>
          <td>{{ item.状态统计['已通过'] ?? 0 }}</td>
          <td>{{ item.状态统计['未受影响'] ?? 0 }}</td>
        </tr>
        <tr v-if="!batches.length">
          <td colspan="6" class="empty-state">还没有复验批次，进入后勾选规则行即可成组复验</td>
        </tr>
      </tbody>
    </table>
    <p v-if="message" class="error-text">{{ message }}</p>
  </article>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listBatches } from '@/api/revalidation-service'
import type { RevalidationBatchSummary } from '@/data/types'

const batches = ref<RevalidationBatchSummary[]>([])
const message = ref('')

onMounted(async () => {
  try {
    batches.value = (await listBatches()).items
  } catch (error) {
    message.value = error instanceof Error ? error.message : '复验批次读取失败'
  }
})
</script>

<style scoped>
.panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin: 12px 0; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.panel h3 { margin: 0 0 4px; font-size: 15px; }
.panel-desc { color: var(--muted); font-size: 12px; margin: 0 0 10px; }
.btn { border: 1px solid var(--border); background: #fff; border-radius: 6px; padding: 6px 12px; cursor: pointer; text-decoration: none; font-size: 13px; }
.btn.primary { background: var(--brand); border-color: var(--brand); color: #fff; }
</style>
