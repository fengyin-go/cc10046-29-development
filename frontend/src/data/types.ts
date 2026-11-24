/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

/* ---------------- 字段复验批次 ---------------- */

export type RuleRow = {
  id: number
  规则标识: string
  来源: string
  校验字段: string
  校验类型: string
  校验参数: string
  原版本: string
  新版本: string
  变更类型: string
  说明: string
  受影响列: string[]
  上游依赖: string[]
  原规则: FieldRule
  新规则: FieldRule
}

export type FieldRule = {
  版本: string
  来源列: string
  目标字段: string
  转换函数: string
  默认取值: string
  依赖列: string[]
}

export type RevalidationField = {
  字段标识: string
  来源: string
  规则标识: string
  校验字段: string
  校验类型: string
  校验参数: string
  变更类型: string
  原版本: string
  新版本: string
  采用版本: string | null
  是否采用新版: boolean
  状态: string
  受影响列: string[]
  上游依赖: string[]
  目标字段: string
  映射版本: string | null
  缺列: string[]
  缺列来源: string[]
  说明: string
}

export type ScopeEntry = {
  来源: string
  校验字段: string
  规则标识: string
  状态: string
  采用版本: string | null
  原版本: string
  新版本: string
  是否采用新版: boolean
  目标字段: string
  映射版本: string | null
  缺列: string[]
  缺列来源: string[]
}

export type EffectiveScope = {
  批次标识: string
  状态: string
  来源: string[]
  版本汇总: Record<string, Record<string, string | null>>
  采用版本明细: Record<string, string | null>
  映射版本: Record<string, string | null>
  待补列: Record<string, string[]>
  字段版本: ScopeEntry[]
}

export type RevalidationFieldSnapshot = {
  来源: string
  校验字段: string
  规则标识: string
  状态: string
  采用版本: string | null
  原版本: string
  新版本: string
  是否采用新版: boolean
  目标字段: string
  映射版本: string | null
  受影响列: string[]
  上游依赖: string[]
  缺列: string[]
  缺列来源: string[]
}

export type RevalidationRound = {
  轮次: number
  动作: string
  时间: string
  说明: string
  状态统计: Record<string, number>
  字段: RevalidationFieldSnapshot[]
  生效范围: EffectiveScope
  补列?: { 来源: string; 列: string }[]
  续做字段?: string[]
  复算字段?: string[]
}

export type RevalidationGroup = {
  来源: string
  字段数: number
  状态统计: Record<string, number>
  字段: string[]
}

export type RevalidationBatchSummary = {
  id: number
  批次标识: string
  申请标识: string
  状态: string
  创建时间: string
  来源: string[]
  字段数: number
  状态统计: Record<string, number>
  规则行: string[]
}

export type RevalidationBatch = {
  id: number
  批次标识: string
  申请标识: string
  状态: string
  创建时间: string
  来源: string[]
  来源列: Record<string, string[]>
  字段: RevalidationField[]
  全部字段: RevalidationField[]
  状态统计: Record<string, number>
  分组: RevalidationGroup[]
  生效范围: EffectiveScope
  复验记录: RevalidationRound[]
  规则行: RuleRow[]
  batch_id?: string
  effective_scope?: EffectiveScope
  fields?: RevalidationField[]
}

export type DryRunField = {
  来源: string
  校验字段: string
  规则标识: string
  状态: string
  采用版本: string | null
  映射版本: string | null
  原版本: string
  新版本: string
  是否采用新版: boolean
  目标字段: string
  来源列: string
  映射值: unknown
  缺列: string[]
  缺列来源: string[]
}

export type DryRunResult = {
  批次: number
  批次标识: string
  试跑来源: string[]
  试跑字段: DryRunField[]
  映射值: Record<string, unknown>
  生效范围: EffectiveScope
  本次生效范围: EffectiveScope
  chain?: string
}
