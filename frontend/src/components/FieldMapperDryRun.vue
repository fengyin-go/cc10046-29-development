<template>
  <article class="panel" data-testid="field-mapper-dry-run">
    <h3>按字段复验批次试跑</h3>
    <p class="panel-desc">
      选择字段复验批次与同组来源，读取该批次实际通过的规则版本运行字段映射试跑；待补字段保持原版本。
    </p>
    <div class="form-row">
      <label class="inline-field">
        <span>复验批次</span>
        <select v-model="batchRef" data-testid="mapper-batch-select">
          <option value="">请选择批次</option>
          <option v-for="item in batches" :key="item.批次标识" :value="item.批次标识">
            {{ item.批次标识 }}（{{ item.状态 }}）
          </option>
        </select>
      </label>
      <label class="inline-field">
        <span>试跑来源</span>
        <select v-model="sources" multiple class="multi-select" data-testid="mapper-source-select">
          <option v-for="source in availableSources" :key="source" :value="source">{{ source }}</option>
        </select>
      </label>
      <button class="btn primary" data-testid="mapper-run" type="button" :disabled="!batchRef" @click="run">
        试跑
      </button>
    </div>

    <p v-if="message" class="error-text" data-testid="mapper-error">{{ message }}</p>

    <template v-if="result">
      <table class="data-table" data-testid="mapper-result">
        <thead>
          <tr>
            <th>来源</th>
            <th>校验字段</th>
            <th>状态</th>
            <th>规则版本</th>
            <th>映射版本</th>
            <th>目标字段</th>
            <th>映射值</th>
            <th>是否采用新版</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in result.试跑字段"
            :key="`${item.来源}-${item.校验字段}`"
            :data-testid="`mapper-field-${item.来源}-${item.校验字段}`"
            :data-version="item.采用版本 ?? ''"
          >
            <td>{{ item.来源 }}</td>
            <td>{{ item.校验字段 }}</td>
            <td>{{ item.状态 }}</td>
            <td>{{ item.采用版本 ?? '—' }}</td>
            <td>{{ item.映射版本 ?? '—' }}</td>
            <td>{{ item.目标字段 }}</td>
            <td>{{ formatValue(item.映射值) }}</td>
            <td>{{ item.是否采用新版 ? '是' : '否' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="hint" data-testid="mapper-scope">
        生效版本：{{ JSON.stringify(result.本次生效范围.版本汇总) }}
      </p>
    </template>
  </article>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import {
  dryRunFieldMapping,
  getFieldMappingScope,
  listBatches,
} from '@/api/revalidation-service'
import type {
  DryRunResult,
  RevalidationBatchSummary,
} from '@/data/types'

const batches = ref<RevalidationBatchSummary[]>([])
const batchRef = ref('')
const sources = ref<string[]>([])
const result = ref<DryRunResult | null>(null)
const message = ref('')
const selectedBatch = computed(() => batches.value.find((item) => item.批次标识 === batchRef.value))
const availableSources = computed(() => selectedBatch.value?.来源 ?? [])

watch(batchRef, () => {
  sources.value = [...availableSources.value]
  result.value = null
  message.value = ''
})

function formatValue(value: unknown) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

async function run() {
  message.value = ''
  try {
    const payload = {
      批次标识: batchRef.value,
      来源: sources.value.length ? sources.value : availableSources.value,
    }
    result.value = await dryRunFieldMapping(payload)
    // 同时核对字段映射侧与批次详情页读到的是同一份生效范围。
    const scope = await getFieldMappingScope(batchRef.value, payload.来源)
    if (JSON.stringify(scope.版本汇总) !== JSON.stringify(result.value.生效范围.版本汇总)) {
      message.value = '生效范围与批次详情不一致，请刷新后重试'
    }
  } catch (error) {
    message.value = error instanceof Error ? error.message : '字段映射试跑失败'
  }
}

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
.panel h3 { margin: 0 0 4px; font-size: 15px; }
.panel-desc { color: var(--muted); font-size: 12px; margin: 0 0 10px; }
.form-row { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.inline-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.inline-field select { border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 13px; }
.multi-select { min-height: 70px; }
.hint { color: var(--muted); font-size: 12px; margin-top: 6px; }
</style>
