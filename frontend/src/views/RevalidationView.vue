<template>
  <section class="page revalidation-page" data-testid="revalidation-page">
    <header class="page-head">
      <div>
        <h2>字段复验批次</h2>
        <p class="page-desc">
          把多个来源的字段校验规则行编成一组，逐条记录实际受影响的列与上游依赖，按实际通过的版本试跑。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" data-testid="refresh-batches" type="button" @click="loadBatches">刷新批次</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text" data-testid="revalidation-error">{{ errorMessage }}</p>

    <div class="revalidation-layout">
      <!-- 规则行选择 -->
      <article class="panel" data-testid="rule-panel">
        <h3>可编入批次的规则行</h3>
        <p class="panel-desc">按来源勾选所需的规则行，跨来源成组复验。</p>
        <table class="data-table">
          <thead>
            <tr>
              <th></th>
              <th>来源</th>
              <th>规则标识</th>
              <th>校验字段</th>
              <th>变更类型</th>
              <th>版本</th>
              <th>上游依赖</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="rule in ruleRows"
              :key="rule.规则标识"
              :data-testid="`rule-row-${rule.规则标识}`"
              :class="{ selected: selectedRules.includes(rule.规则标识) }"
              @click="toggleRule(rule.规则标识)"
            >
              <td>
                <input
                  type="checkbox"
                  :data-testid="`rule-check-${rule.规则标识}`"
                  :value="rule.规则标识"
                  v-model="selectedRules"
                  @click.stop
                />
              </td>
              <td>{{ rule.来源 }}</td>
              <td>{{ rule.规则标识 }}</td>
              <td>{{ rule.校验字段 }}</td>
              <td>{{ rule.变更类型 }}</td>
              <td>{{ rule.原版本 }}<template v-if="rule.新版本 !== rule.原版本"> → {{ rule.新版本 }}</template></td>
              <td>{{ rule.上游依赖.length ? rule.上游依赖.join('、') : '—' }}</td>
            </tr>
            <tr v-if="!ruleRows.length">
              <td colspan="7" class="empty-state">暂无可选规则行</td>
            </tr>
          </tbody>
        </table>
        <div class="page-actions form-actions">
          <label class="inline-field">
            <span>申请标识</span>
            <input v-model="applicationId" data-testid="application-id" placeholder="APP-字段复验-01" />
          </label>
          <button
            class="btn primary"
            data-testid="create-batch"
            type="button"
            :disabled="!selectedRules.length || creating"
            @click="createSelectedBatch"
          >
            {{ creating ? '复验中…' : '成组复验' }}
          </button>
        </div>
      </article>

      <!-- 批次列表 -->
      <article class="panel" data-testid="batch-list-panel">
        <h3>复验批次</h3>
        <p class="panel-desc">选中批次查看待补、已通过、未受影响的字段。</p>
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
            <tr
              v-for="batch in batches"
              :key="batch.批次标识"
              :data-testid="`batch-row-${batch.批次标识}`"
              :class="{ selected: activeBatch === batch.批次标识 }"
              @click="openBatch(batch.批次标识)"
            >
              <td>{{ batch.批次标识 }}</td>
              <td>{{ batch.状态 }}</td>
              <td>{{ batch.来源.join('、') }}</td>
              <td data-testid="batch-pending-count">{{ batch.状态统计['待补'] ?? 0 }}</td>
              <td>{{ batch.状态统计['已通过'] ?? 0 }}</td>
              <td>{{ batch.状态统计['未受影响'] ?? 0 }}</td>
            </tr>
            <tr v-if="!batches.length">
              <td colspan="6" class="empty-state">还没有复验批次，先勾选规则行成组复验</td>
            </tr>
          </tbody>
        </table>
      </article>
    </div>

    <article v-if="batch" class="panel batch-detail" data-testid="batch-detail">
      <header class="detail-head">
        <div>
          <h3>{{ batch.批次标识 }} <span class="tag" :data-status="batch.状态">{{ batch.状态 }}</span></h3>
          <p class="panel-desc">
            申请 {{ batch.申请标识 }} · 来源 {{ batch.来源.join('、') }} · 创建于 {{ batch.创建时间 }}
          </p>
        </div>
        <div class="page-actions">
          <button class="btn" data-testid="revalidate-batch" type="button" @click="revalidateActive">整组复验</button>
          <button class="btn" data-testid="submit-batch" type="button" @click="submitActive">提交结果</button>
        </div>
      </header>

      <div class="stat-row compact">
        <article
          v-for="state in fieldStates"
          :key="state"
          class="stat-card clickable"
          :class="{ active: stateFilter === state }"
          :data-testid="`state-card-${state}`"
          @click="setStateFilter(state)"
        >
          <span class="stat-label">{{ state }}</span>
          <strong class="stat-value">{{ batch.状态统计[state] ?? 0 }}</strong>
        </article>
        <article
          class="stat-card clickable"
          :class="{ active: stateFilter === '全部' }"
          data-testid="state-card-全部"
          @click="setStateFilter('全部')"
        >
          <span class="stat-label">全部</span>
          <strong class="stat-value">{{ batch.全部字段.length }}</strong>
        </article>
      </div>

      <h4>字段（当前筛选：{{ stateFilter }}）</h4>
      <table class="data-table">
        <thead>
          <tr>
            <th>来源</th>
            <th>校验字段</th>
            <th>状态</th>
            <th>变更类型</th>
            <th>原版本</th>
            <th>新版本</th>
            <th>采用版本</th>
            <th>是否采用新版</th>
            <th>受影响列</th>
            <th>上游依赖</th>
            <th>缺列</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="field in visibleFields"
            :key="field.字段标识"
            :data-testid="`field-row-${field.字段标识}`"
            :data-state="field.状态"
            :data-version="field.采用版本 ?? ''"
          >
            <td>{{ field.来源 }}</td>
            <td>{{ field.校验字段 }}</td>
            <td>{{ field.状态 }}</td>
            <td>{{ field.变更类型 }}</td>
            <td>{{ field.原版本 }}</td>
            <td>{{ field.新版本 }}</td>
            <td data-testid="field-adopted-version">{{ field.采用版本 ?? '—' }}</td>
            <td>{{ field.是否采用新版 ? '是' : '否' }}</td>
            <td>{{ field.受影响列.length ? field.受影响列.join('、') : '—' }}</td>
            <td>{{ field.上游依赖.length ? field.上游依赖.join('、') : '—' }}</td>
            <td>{{ field.缺列.length ? field.缺列.join('、') : '—' }}</td>
          </tr>
          <tr v-if="!visibleFields.length">
            <td colspan="11" class="empty-state">该筛选下没有字段</td>
          </tr>
        </tbody>
      </table>

      <section class="sub-block">
        <h4>来源分组与可补列</h4>
        <table class="data-table">
          <thead>
            <tr>
              <th>来源</th>
              <th>字段</th>
              <th>待补</th>
              <th>已通过</th>
              <th>未受影响</th>
              <th>现有列</th>
              <th>补列</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in batch.分组" :key="group.来源" :data-testid="`group-row-${group.来源}`">
              <td>{{ group.来源 }}</td>
              <td>{{ group.字段.join('、') }}</td>
              <td>{{ group.状态统计['待补'] ?? 0 }}</td>
              <td>{{ group.状态统计['已通过'] ?? 0 }}</td>
              <td>{{ group.状态统计['未受影响'] ?? 0 }}</td>
              <td>{{ (batch.来源列[group.来源] || []).join('、') || '—' }}</td>
              <td>
                <input
                  v-model="supplementInput[group.来源]"
                  class="supplement-input"
                  :data-testid="`supplement-${group.来源}`"
                  placeholder="缺失列，逗号分隔"
                />
                <button
                  class="link"
                  type="button"
                  :data-testid="`resume-${group.来源}`"
                  :disabled="!(group.状态统计['待补'] ?? 0)"
                  @click="resumeSource(group.来源)"
                >
                  提交续做
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="hint">补列续做只重算受补列影响的字段，已确认的字段不会换版本。</p>
      </section>

      <section class="sub-block">
        <h4>同组来源试跑</h4>
        <p class="panel-desc">
          试跑读取该批次实际通过的规则版本与映射值；待补字段仍显示原版本，不会显示为已采用新版。
        </p>
        <label class="inline-field">
          <span>试跑来源</span>
          <select v-model="dryRunSources" multiple data-testid="dry-run-sources" class="multi-select">
            <option v-for="source in batch.来源" :key="source" :value="source">{{ source }}</option>
          </select>
        </label>
        <label class="inline-field wide">
          <span>样例数据（JSON，可按来源分组）</span>
          <textarea v-model="sampleText" data-testid="dry-run-sample" rows="3" />
        </label>
        <div class="page-actions">
          <button class="btn primary" data-testid="run-dry-run" type="button" @click="runDryRun">
            运行试跑
          </button>
          <button class="btn" data-testid="check-scope" type="button" @click="checkScope">
            核对两处生效范围
          </button>
        </div>

        <table v-if="dryRun" class="data-table" data-testid="dry-run-result">
          <thead>
            <tr>
              <th>来源</th>
              <th>校验字段</th>
              <th>状态</th>
              <th>规则版本</th>
              <th>映射版本</th>
              <th>来源列</th>
              <th>映射值</th>
              <th>是否采用新版</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in dryRun.试跑字段"
              :key="`${item.来源}-${item.校验字段}`"
              :data-testid="`dry-run-field-${item.来源}-${item.校验字段}`"
              :data-version="item.采用版本 ?? ''"
            >
              <td>{{ item.来源 }}</td>
              <td>{{ item.校验字段 }}</td>
              <td>{{ item.状态 }}</td>
              <td>{{ item.采用版本 ?? '—' }}</td>
              <td>{{ item.映射版本 ?? '—' }}</td>
              <td>{{ item.来源列 }}</td>
              <td>{{ formatValue(item.映射值) }}</td>
              <td>{{ item.是否采用新版 ? '是' : '否' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="scopeCheck" class="hint scope-check" data-testid="scope-check-result">
          批次详情与字段映射两处生效范围：{{ scopeCheck }}
        </p>
      </section>

      <section class="sub-block">
        <h4>复验记录</h4>
        <table class="data-table">
          <thead>
            <tr>
              <th>轮次</th>
              <th>动作</th>
              <th>时间</th>
              <th>说明</th>
              <th>字段结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in batch.复验记录" :key="entry.轮次" :data-testid="`round-row-${entry.轮次}`">
              <td>{{ entry.轮次 }}</td>
              <td>{{ entry.动作 }}</td>
              <td>{{ entry.时间 }}</td>
              <td>{{ entry.说明 }}</td>
              <td class="round-fields">
                <span
                  v-for="snapshot in entry.字段"
                  :key="`${snapshot.来源}-${snapshot.校验字段}`"
                  class="round-chip"
                  :data-state="snapshot.状态"
                >
                  {{ snapshot.来源 }}/{{ snapshot.校验字段 }} · {{ snapshot.状态 }} · {{ snapshot.采用版本 }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="page-actions">
          <label class="inline-field">
            <span>回看轮次</span>
            <select v-model.number="roundNo" data-testid="round-select">
              <option v-for="entry in batch.复验记录" :key="entry.轮次" :value="entry.轮次">
                第 {{ entry.轮次 }} 轮
              </option>
            </select>
          </label>
          <button class="btn" data-testid="load-round" type="button" @click="loadRound">载入该轮筛选</button>
        </div>
        <table v-if="roundSnapshot" class="data-table" data-testid="round-snapshot">
          <thead>
            <tr>
              <th>来源</th>
              <th>校验字段</th>
              <th>当时状态</th>
              <th>当时采用版本</th>
              <th>当时映射版本</th>
              <th>当时受影响列</th>
              <th>当时缺列</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in roundSnapshot.字段"
              :key="`${item.来源}-${item.校验字段}`"
              :data-testid="`round-field-${item.来源}-${item.校验字段}`"
            >
              <td>{{ item.来源 }}</td>
              <td>{{ item.校验字段 }}</td>
              <td>{{ item.状态 }}</td>
              <td>{{ item.采用版本 ?? '—' }}</td>
              <td>{{ item.映射版本 ?? '—' }}</td>
              <td>{{ item.受影响列.length ? item.受影响列.join('、') : '—' }}</td>
              <td>{{ item.缺列.length ? item.缺列.join('、') : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import {
  createBatch,
  dryRunBatch,
  dryRunFieldMapping,
  getBatch,
  getBatchScope,
  getFieldMappingScope,
  getRound,
  listBatches,
  listRuleRows,
  revalidateBatch,
  resumeBatch,
  submitBatch,
} from '@/api/revalidation-service'
import type {
  DryRunResult,
  RevalidationBatch,
  RevalidationBatchSummary,
  RevalidationRound,
  RuleRow,
} from '@/data/types'

const fieldStates = ['待补', '已通过', '未受影响']

const ruleRows = ref<RuleRow[]>([])
const selectedRules = ref<string[]>([])
const applicationId = ref('APP-字段复验-01')
const batches = ref<RevalidationBatchSummary[]>([])
const activeBatch = ref('')
const batch = ref<RevalidationBatch | null>(null)
const stateFilter = ref('全部')
const supplementInput = ref<Record<string, string>>({})
const dryRunSources = ref<string[]>([])
const dryRun = ref<DryRunResult | null>(null)
const scopeCheck = ref('')
const roundNo = ref(1)
const roundSnapshot = ref<RevalidationRound | null>(null)
const sampleText = ref(
  JSON.stringify(
    {
      甲: { 商品名称: '旧名称', 新名称列: '新名称', 型号: 'M-1' },
      乙: { 价格: '12', 基价: '18' },
      丙: { 重量: '3.5', 产地: '杭州' },
    },
    null,
    2,
  ),
)
const creating = ref(false)
const errorMessage = ref('')

const visibleFields = computed(() => batch.value?.字段 ?? [])

function toggleRule(ruleId: string) {
  const index = selectedRules.value.indexOf(ruleId)
  if (index >= 0) selectedRules.value.splice(index, 1)
  else selectedRules.value.push(ruleId)
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function setStateFilter(state: string) {
  stateFilter.value = state
}async function refreshBatch() {
  if (!activeBatch.value) return
  const state = stateFilter.value === '全部' ? undefined : stateFilter.value
  batch.value = await getBatch(activeBatch.value, state)
}

async function loadBatches() {
  errorMessage.value = ''
  try {
    const payload = await listBatches()
    batches.value = payload.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '复验批次读取失败'
  }
}

async function loadRules() {
  try {
    const payload = await listRuleRows()
    ruleRows.value = payload.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '规则行读取失败'
  }
}

async function openBatch(batchRef: string) {
  errorMessage.value = ''
  activeBatch.value = batchRef
  stateFilter.value = '全部'
  dryRun.value = null
  scopeCheck.value = ''
  roundSnapshot.value = null
  try {
    await refreshBatch()
    if (batch.value) {
      dryRunSources.value = [...batch.value.来源]
      roundNo.value = batch.value.复验记录[0]?.轮次 ?? 1
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '复验批次详情读取失败'
  }
}

async function createSelectedBatch() {
  creating.value = true
  errorMessage.value = ''
  try {
    const detail = await createBatch({
      规则行: selectedRules.value,
      申请标识: applicationId.value,
    })
    selectedRules.value = []
    await loadBatches()
    await openBatch(detail.批次标识)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '成组复验失败'
  } finally {
    creating.value = false
  }
}

async function revalidateActive() {
  if (!batch.value) return
  errorMessage.value = ''
  const batchRef = batch.value.批次标识
  try {
    await revalidateBatch(batchRef)
    await refreshBatch()
    await loadBatches()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '整组复验失败'
  }
}

async function submitActive() {
  if (!batch.value) return
  errorMessage.value = ''
  const batchRef = batch.value.批次标识
  try {
    await submitBatch(batchRef)
    await refreshBatch()
    await loadBatches()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '复验提交失败'
  }
}

async function resumeSource(source: string) {
  if (!batch.value) return
  errorMessage.value = ''
  const raw = supplementInput.value[source] ?? ''
  const columns = raw
    .split(/[,，、\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (!columns.length) {
    errorMessage.value = `请先填写 ${source} 要补的列`
    return
  }
  try {
    await resumeBatch(batch.value.批次标识, {
      补列: [{ 来源: source, 列: columns }],
    })
    supplementInput.value[source] = ''
    await refreshBatch()
    await loadBatches()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '补列续做失败'
  }
}

function parseSample(): Record<string, unknown> {
  try {
    const parsed = JSON.parse(sampleText.value || '{}')
    return typeof parsed === 'object' && parsed !== null ? parsed : {}
  } catch {
    throw new Error('样例数据不是合法 JSON')
  }
}

async function runDryRun() {
  if (!batch.value) return
  errorMessage.value = ''
  try {
    const sample = parseSample()
    const sources = dryRunSources.value.length ? dryRunSources.value : [...batch.value.来源]
    dryRun.value = await dryRunBatch(batch.value.批次标识, { 来源: sources, 样例数据: sample })
    scopeCheck.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '试跑失败'
  }
}

async function checkScope() {
  if (!batch.value) return
  errorMessage.value = ''
  try {
    const sources = dryRunSources.value.length ? dryRunSources.value : [...batch.value.来源]
    const [batchScope, mapperScope, mapperDryRun] = await Promise.all([
      getBatchScope(batch.value.批次标识, sources),
      getFieldMappingScope(batch.value.批次标识, sources),
      dryRunFieldMapping({
        批次标识: batch.value.批次标识,
        来源: sources,
        样例数据: parseSample(),
      }),
    ])
    const left = JSON.stringify(batchScope.采用版本明细)
    const right = JSON.stringify(mapperScope.采用版本明细)
    const consistent = left === right
    scopeCheck.value = consistent
      ? `一致（${sources.join('、')}：${left}）`
      : `不一致：批次 ${left} / 字段映射 ${right}`
    if (!dryRun.value) dryRun.value = mapperDryRun
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生效范围核对失败'
  }
}

async function loadRound() {
  if (!batch.value) return
  errorMessage.value = ''
  try {
    roundSnapshot.value = await getRound(batch.value.批次标识, roundNo.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '复验轮次读取失败'
  }
}

watch(stateFilter, () => {
  if (activeBatch.value) void refreshBatch()
})

onMounted(async () => {
  await Promise.all([loadRules(), loadBatches()])
  if (batches.value.length) await openBatch(batches.value[batches.value.length - 1].批次标识)
})
</script>

<style scoped>
.revalidation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.panel h3 { margin: 0 0 4px; font-size: 15px; }
.panel h4 { margin: 14px 0 8px; font-size: 14px; }
.panel-desc { color: var(--muted); font-size: 12px; margin: 0 0 10px; }
.hint { color: var(--muted); font-size: 12px; margin-top: 6px; }
.form-actions { margin-top: 10px; align-items: flex-end; }
.inline-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); margin-right: 10px; }
.inline-field input, .inline-field select, .inline-field textarea {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  color: #1f2937;
}
.inline-field.wide { width: 100%; }
.inline-field textarea { font-family: monospace; }
.multi-select { min-height: 76px; }
.data-table tr.selected { background: #eff6ff; }
.data-table tr { cursor: pointer; }
.batch-detail { margin-top: 4px; }
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.tag {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #eef2ff;
  color: #1f6feb;
}
.tag[data-status='待补'] { background: #fef3c7; color: #92400e; }
.tag[data-status='已完成'] { background: #dcfce7; color: #166534; }
.stat-row.compact .stat-card { padding: 8px 10px; }
.stat-card.clickable { cursor: pointer; }
.stat-card.active { border-color: var(--brand); box-shadow: inset 0 0 0 1px var(--brand); }
.sub-block { margin-top: 16px; border-top: 1px dashed var(--border); padding-top: 8px; }
.supplement-input { border: 1px solid var(--border); border-radius: 6px; padding: 4px 6px; font-size: 12px; width: 110px; margin-right: 6px; }
.round-fields { display: flex; flex-wrap: wrap; gap: 4px; }
.round-chip { display: inline-block; font-size: 11px; padding: 2px 6px; border-radius: 8px; background: #f1f5f9; }
.round-chip[data-state='待补'] { background: #fef3c7; color: #92400e; }
.round-chip[data-state='已通过'] { background: #dcfce7; color: #166534; }
.round-chip[data-state='未受影响'] { background: #e2e8f0; color: #475569; }
.scope-check { color: #166534; }
</style>
