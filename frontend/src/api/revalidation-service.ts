/** 字段复验批次与字段映射试跑接口。 */
import { request } from './client'
import type {
  DryRunResult,
  EffectiveScope,
  PageResult,
  RevalidationBatch,
  RevalidationBatchSummary,
  RevalidationRound,
  RuleRow,
} from '@/data/types'

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : fallback
    throw new Error(detail)
  }
  return payload as T
}

export async function listRuleRows(params: { source?: string; keyword?: string } = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value) as [string, string][],
  ).toString()
  const response = await request(`/api/field-revalidation/rules?${query}`)
  return await readJson<{ items: RuleRow[]; total: number; sources: string[] }>(
    response,
    '规则行读取失败',
  )
}

export async function listBatches(params: { status?: string; source?: string } = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value) as [string, string][],
  ).toString()
  const response = await request(`/api/field-revalidation/batches?${query}`)
  return await readJson<PageResult & { items: RevalidationBatchSummary[] }>(
    response,
    '复验批次读取失败',
  )
}

export async function createBatch(payload: {
  规则行: (string | number)[]
  来源列?: Record<string, string[]>
  申请标识?: string
}) {
  const response = await request('/api/field-revalidation/batches', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return await readJson<RevalidationBatch>(response, '复验批次创建失败')
}

export async function getBatch(batchRef: string, state?: string) {
  const query = state && state !== '全部' ? `?state=${encodeURIComponent(state)}` : ''
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}${query}`,
  )
  return await readJson<RevalidationBatch>(response, '复验批次详情读取失败')
}

export async function revalidateBatch(batchRef: string) {
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}/revalidate`,
    { method: 'POST', body: '{}' },
  )
  return await readJson<RevalidationBatch>(response, '整组复验失败')
}

export async function submitBatch(batchRef: string) {
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}/submit`,
    { method: 'POST', body: '{}' },
  )
  return await readJson<RevalidationBatch>(response, '复验提交失败')
}

export async function resumeBatch(
  batchRef: string,
  payload: { 补列: { 来源: string; 列: string[] }[] },
) {
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}/resume`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
  return await readJson<RevalidationBatch>(response, '补列续做失败')
}

export async function getRound(batchRef: string, roundNo: number) {
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}/rounds/${roundNo}`,
  )
  return await readJson<RevalidationRound>(response, '复验轮次读取失败')
}

export async function getBatchScope(batchRef: string, sources: string[] = []) {
  const query = sources.length ? `?sources=${encodeURIComponent(sources.join(','))}` : ''
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}/scope${query}`,
  )
  return await readJson<EffectiveScope>(response, '生效范围读取失败')
}

export async function dryRunBatch(
  batchRef: string,
  payload: { 来源: string[]; 样例数据?: Record<string, unknown> },
) {
  const response = await request(
    `/api/field-revalidation/batches/${encodeURIComponent(batchRef)}/dry-run`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
  return await readJson<DryRunResult>(response, '试跑失败')
}

/** 字段映射试跑：走字段映射模块，读同一批复验结果。 */
export async function dryRunFieldMapping(payload: {
  批次标识: string
  来源: string[]
  样例数据?: Record<string, unknown>
}) {
  const response = await request('/api/field-mapper/dry-run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return await readJson<DryRunResult>(response, '字段映射试跑失败')
}

/** 字段映射侧读取生效范围，用于和批次详情页做一致性核对。 */
export async function getFieldMappingScope(batchRef: string, sources: string[] = []) {
  const query = new URLSearchParams({ batch_id: batchRef })
  if (sources.length) query.set('sources', sources.join(','))
  const response = await request(`/api/field-mapper/scope?${query.toString()}`)
  return await readJson<EffectiveScope>(response, '字段映射生效范围读取失败')
}
