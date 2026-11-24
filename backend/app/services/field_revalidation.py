"""字段复验批次领域服务。

一个字段复验批次可以把多个来源（甲/乙/丙…）的校验规则行编成一组，
选中规则行后成组复验，并逐条记录实际受影响的列、上游依赖和最终采用的版本。

核心规则：
- 规则未变更的来源（如丙的重量）标记为「未受影响」，沿用原版本；
- 规则已变更且上游依赖齐全的来源（如甲换新名称列）标记为「已通过」，采用新版本；
- 规则已变更但依赖列缺失的来源（如乙的结算价）标记为「待补」，保留缺列来源和原规则，
  试跑时绝不能把尚未通过的字段显示成已采用新版本；
- 后续补列只续做受补列影响的字段，其他已确认结果保持不变；
- 同一批次重复提交时，已经确认的字段版本不会被替换。

字段映射的试跑统一从这里读取「实际通过的规则版本和生效范围」，
保证批次详情页与字段映射试跑读到的生效范围完全一致。
"""
from __future__ import annotations

import copy
import time
from typing import Any

# 复验状态
STATE_PENDING = "待补"
STATE_PASSED = "已通过"
STATE_UNCHANGED = "未受影响"
STATE_WAIT = "待复验"
FIELD_STATES = [STATE_PENDING, STATE_PASSED, STATE_UNCHANGED]

BATCH_PENDING = "待补"
BATCH_DONE = "已完成"
BATCH_RUNNING = "复验中"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


# ---------------------------------------------------------------- 默认场景
# 同一申请里三个来源都有规则行：甲换列、乙缺依赖、丙未修改。
DEFAULT_SOURCE_COLUMNS: dict[str, list[str]] = {
    "甲": ["商品名称", "新名称列", "型号"],
    "乙": ["结算价"],
    "丙": ["重量", "产地"],
}

DEFAULT_RULE_ROWS: list[dict[str, Any]] = [
    {
        "id": 1,
        "规则标识": "VR-甲-商品名称-01",
        "来源": "甲",
        "校验字段": "商品名称",
        "校验类型": "非空",
        "校验参数": "不允许为空",
        "原版本": "v1",
        "新版本": "v2",
        "变更类型": "字段换列",
        "说明": "甲把商品名称改读新名称列",
        "原规则": {
            "版本": "v1",
            "来源列": "商品名称",
            "目标字段": "product_name",
            "转换函数": "trim",
            "默认取值": "",
            "依赖列": [],
        },
        "新规则": {
            "版本": "v2",
            "来源列": "新名称列",
            "目标字段": "product_name",
            "转换函数": "trim",
            "默认取值": "",
            "依赖列": ["新名称列"],
        },
        "受影响列": ["商品名称", "新名称列"],
        "上游依赖": ["新名称列"],
    },
    {
        "id": 2,
        "规则标识": "VR-乙-结算价-01",
        "来源": "乙",
        "校验字段": "结算价",
        "校验类型": "数值范围",
        "校验参数": ">=0",
        "原版本": "v1",
        "新版本": "v2",
        "变更类型": "依赖删除",
        "说明": "乙删掉了价格依赖，结算价改读基价列",
        "原规则": {
            "版本": "v1",
            "来源列": "价格",
            "目标字段": "settlement_price",
            "转换函数": "int",
            "默认取值": "0",
            "依赖列": ["价格"],
        },
        "新规则": {
            "版本": "v2",
            "来源列": "基价",
            "目标字段": "settlement_price",
            "转换函数": "int",
            "默认取值": "0",
            "依赖列": ["基价"],
        },
        "受影响列": ["结算价", "价格", "基价"],
        "上游依赖": ["基价"],
    },
    {
        "id": 3,
        "规则标识": "VR-丙-重量-01",
        "来源": "丙",
        "校验字段": "重量",
        "校验类型": "数值范围",
        "校验参数": ">=0",
        "原版本": "v1",
        "新版本": "v1",
        "变更类型": "未变更",
        "说明": "丙的重量未修改，沿用旧版",
        "原规则": {
            "版本": "v1",
            "来源列": "重量",
            "目标字段": "weight",
            "转换函数": "",
            "默认取值": "0",
            "依赖列": ["重量"],
        },
        "新规则": {
            "版本": "v1",
            "来源列": "重量",
            "目标字段": "weight",
            "转换函数": "",
            "默认取值": "0",
            "依赖列": ["重量"],
        },
        "受影响列": [],
        "上游依赖": [],
    },
]


def _normalize_rule(row: dict[str, Any], fallback_id: int = 0) -> dict[str, Any]:
    """把外部传入的规则行补齐成服务内部统一结构。"""
    rule = copy.deepcopy(row)
    source = str(rule.get("来源") or rule.get("source") or "").strip()
    field = str(rule.get("校验字段") or rule.get("field") or "").strip()
    if not source:
        raise ValueError("规则行缺少「来源」")
    if not field:
        raise ValueError("规则行缺少「校验字段」")
    rule_id = str(rule.get("规则标识") or rule.get("id") or f"VR-{source}-{field}-{fallback_id}")
    old_rule = copy.deepcopy(rule.get("原规则") or {})
    new_rule = copy.deepcopy(rule.get("新规则") or {})

    old_version = str(
        rule.get("原版本") or old_rule.get("版本") or rule.get("old_version") or "v1"
    )
    new_version = str(
        rule.get("新版本") or new_rule.get("版本") or rule.get("new_version") or old_version
    )
    old_col = str(
        rule.get("原列") or old_rule.get("来源列") or rule.get("old_column") or field
    )
    new_col = str(
        rule.get("新列") or new_rule.get("来源列") or rule.get("new_column") or old_col
    )
    target = str(
        rule.get("目标字段") or new_rule.get("目标字段") or old_rule.get("目标字段") or field
    )

    old_rule.update({
        "版本": old_version,
        "来源列": old_col,
        "目标字段": old_rule.get("目标字段") or target,
        "转换函数": old_rule.get("转换函数", rule.get("转换函数", "")),
        "默认取值": old_rule.get("默认取值", rule.get("默认取值", "")),
    })
    old_rule.setdefault("依赖列", list(rule.get("上游依赖") or []))
    new_rule.update({
        "版本": new_version,
        "来源列": new_col,
        "目标字段": new_rule.get("目标字段") or target,
        "转换函数": new_rule.get("转换函数", rule.get("转换函数", "")),
        "默认取值": new_rule.get("默认取值", rule.get("默认取值", "")),
    })
    new_rule.setdefault(
        "依赖列", list(rule.get("上游依赖") or ([new_col] if new_col else [])))

    change_type = str(
        rule.get("变更类型") or rule.get("change_type")
        or ("未变更" if new_version == old_version and old_col == new_col else "规则修改")
    )
    dependencies = list(rule.get("上游依赖") or new_rule.get("依赖列") or [])
    if change_type == "未变更" or new_version == old_version and old_col == new_col:
        change_type = "未变更"
        dependencies = []
        affected: list[str] = []
    else:
        affected = list(rule.get("受影响列") or [])
        if not affected:
            affected = [field]
            for column in (old_col, new_col, *dependencies):
                if column and column not in affected:
                    affected.append(column)

    rule.update({
        "规则标识": rule_id,
        "来源": source,
        "校验字段": field,
        "校验类型": rule.get("校验类型") or "非空",
        "校验参数": rule.get("校验参数") or "",
        "原版本": old_version,
        "新版本": new_version,
        "变更类型": change_type,
        "原规则": old_rule,
        "新规则": new_rule,
        "上游依赖": dependencies,
        "受影响列": affected,
        "说明": rule.get("说明") or "",
    })
    return rule


class FieldRevalidationService:
    """字段复验批次仓储与业务规则。"""

    MODULE = "field_revalidation"
    ENTITY = "字段复验批次"

    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] = [
            _normalize_rule(row, index + 1)
            for index, row in enumerate(copy.deepcopy(DEFAULT_RULE_ROWS))
        ]
        self._source_columns: dict[str, list[str]] = copy.deepcopy(DEFAULT_SOURCE_COLUMNS)
        self._batches: list[dict[str, Any]] = []
        self._next_id = 1

    # ------------------------------------------------------------ 规则行
    def list_rule_rows(
        self,
        *,
        source: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [copy.deepcopy(row) for row in self._rules]
        if source:
            rows = [row for row in rows if str(row.get("来源")) == source]
        if keyword:
            needle = keyword.casefold()
            rows = [
                row for row in rows
                if needle in str(row.get("规则标识", "")).casefold()
                or needle in str(row.get("校验字段", "")).casefold()
                or needle in str(row.get("来源", "")).casefold()
            ]
        return rows

    def _find_rule_by_ref(self, ref: Any) -> dict[str, Any] | None:
        text = str(ref)
        for row in self._rules:
            if text in {str(row.get("规则标识")), str(row.get("id"))}:
                return row
        return None

    def _resolve_rule_entry(self, entry: Any, index: int) -> dict[str, Any]:
        if isinstance(entry, (int, str)):
            found = self._find_rule_by_ref(entry)
            if found is None:
                raise ValueError(f"规则行 {entry} 不存在")
            return copy.deepcopy(found)
        if isinstance(entry, dict):
            ref = entry.get("规则标识") or entry.get("id") or entry.get("rule_id")
            base = self._find_rule_by_ref(ref) if ref is not None else None
            merged = copy.deepcopy(base) if base else {}
            merged.update(copy.deepcopy(entry))
            return _normalize_rule(merged, index)
        raise ValueError(f"无法识别的规则行：{entry!r}")

    # ------------------------------------------------------------ 批次
    def create_batch(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        selection_keys = ("规则行", "rule_rows", "rule_ids", "rule_id", "规则")
        chosen_key = next((key for key in selection_keys if key in payload), None)
        selections = payload[chosen_key] if chosen_key else None
        sources = payload.get("来源") or payload.get("sources") or []

        if chosen_key is None and not sources:
            # 两个都没给时，默认把全部规则行编入批次。
            selected = list(self._rules)
        elif chosen_key is None:
            selected = [
                row for row in self._rules
                if row.get("来源") in sources
            ]
        elif selections is None:
            selected = []
        elif isinstance(selections, (str, int, dict)):
            selected = [self._resolve_rule_entry(selections, 1)]
        elif isinstance(selections, (list, tuple)):
            selected = [
                self._resolve_rule_entry(entry, index + 1)
                for index, entry in enumerate(selections)
            ]
        else:
            raise ValueError(f"无法识别的规则行选择：{selections!r}")

        if not selected:
            raise ValueError("请至少选择一行规则进行成组复验")

        source_names: list[str] = []
        for rule in selected:
            if rule["来源"] not in source_names:
                source_names.append(rule["来源"])

        columns = copy.deepcopy(self._source_columns)
        # 支持两种写法：
        #   {"来源列": {"甲": ["商品名称"]}}            → 覆盖该来源的可用列（可用于模拟缺列）
        #   {"来源列": [{"来源": "乙", "列": [...]}]}  → 追加列
        extra_columns = payload.get("来源列") or payload.get("source_columns")
        if isinstance(extra_columns, dict):
            for source, values in extra_columns.items():
                columns[str(source)] = [str(column) for column in values or []]
        elif isinstance(extra_columns, list):
            for extra in extra_columns:
                if isinstance(extra, dict) and extra.get("来源") and extra.get("列"):
                    columns.setdefault(str(extra["来源"]), [])
                    for column in extra["列"]:
                        if column not in columns[str(extra["来源"])]:
                            columns[str(extra["来源"])].append(str(column))
        for source in source_names:
            columns.setdefault(source, [])

        batch_id = self._next_id
        self._next_id += 1
        batch_code = str(
            payload.get("批次标识") or payload.get("batch_id") or f"FRB-{batch_id:04d}"
        )
        if self.find_batch(batch_code) is not None:
            raise ValueError(f"批次标识 {batch_code} 已存在")

        batch: dict[str, Any] = {
            "id": batch_id,
            "批次标识": batch_code,
            "申请标识": str(payload.get("申请标识") or payload.get("application_id") or "APP-字段复验-01"),
            "状态": BATCH_RUNNING,
            "创建时间": _now(),
            "来源": source_names,
            "来源列": columns,
            "规则行": copy.deepcopy(selected),
            "字段": [],
            "复验记录": [],
        }
        for rule in selected:
            batch["字段"].append(self._field_from_rule(rule))

        # 首次整组复验：创建即完成一次全量计算。
        self._evaluate_batch(batch, preserve_confirmed=False)
        self._refresh_batch_status(batch)
        self._append_round(batch, "成组复验", 说明="按选中规则行执行整组复验")
        self._batches.append(batch)
        return self._detail(batch, alias=True)

    def _field_from_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        return {
            "字段标识": f"{rule['来源']}-{rule['校验字段']}",
            "来源": rule["来源"],
            "规则标识": rule["规则标识"],
            "校验字段": rule["校验字段"],
            "校验类型": rule.get("校验类型", ""),
            "校验参数": rule.get("校验参数", ""),
            "变更类型": rule["变更类型"],
            "原版本": rule["原版本"],
            "新版本": rule["新版本"],
            "采用版本": None,
            "是否采用新版": False,
            "状态": STATE_WAIT,
            "受影响列": list(rule.get("受影响列") or []),
            "上游依赖": list(rule.get("上游依赖") or []),
            "原规则": copy.deepcopy(rule["原规则"]),
            "新规则": copy.deepcopy(rule["新规则"]),
            "生效规则": None,
            "缺列": [],
            "缺列来源": [],
            "目标字段": rule["新规则"].get("目标字段") or rule["校验字段"],
            "映射版本": None,
            "说明": rule.get("说明", ""),
        }

    def find_batch(self, ref: Any) -> dict[str, Any] | None:
        text = str(ref)
        for batch in self._batches:
            if text in {str(batch["id"]), str(batch["批次标识"])}:
                return batch
        return None

    def get_batch(self, ref: Any, state: str | None = None) -> dict[str, Any] | None:
        batch = self.find_batch(ref)
        if batch is None:
            return None
        return self._detail(batch, state=state, alias=True)

    def list_batches(
        self,
        *,
        status: str | None = None,
        source: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(self._batches)
        if status:
            rows = [batch for batch in rows if batch.get("状态") == status]
        if source:
            rows = [batch for batch in rows if source in batch.get("来源", [])]
        total = len(rows)
        start = (page - 1) * size
        items = [
            {
                "id": batch["id"],
                "批次标识": batch["批次标识"],
                "申请标识": batch["申请标识"],
                "状态": batch["状态"],
                "创建时间": batch["创建时间"],
                "来源": list(batch["来源"]),
                "字段数": len(batch["字段"]),
                "状态统计": self._state_counts(batch),
                "规则行": [rule["规则标识"] for rule in batch["规则行"]],
            }
            for batch in rows[start:start + size]
        ]
        return items, total

    # ------------------------------------------------------------ 复验
    @staticmethod
    def _missing_columns(field: dict[str, Any], columns: dict[str, Any]) -> list[str]:
        if field.get("变更类型") == "未变更":
            return []
        rule = field.get("新规则") or {}
        required: list[str] = [str(rule.get("来源列") or "")]
        required.extend(str(column) for column in rule.get("依赖列") or [])
        required.extend(str(column) for column in field.get("上游依赖") or [])
        available = {str(column) for column in columns.get(field["来源"], [])}
        missing: list[str] = []
        for column in required:
            if column and column not in available and column not in missing:
                missing.append(column)
        return missing

    def _evaluate_field(
        self,
        batch: dict[str, Any],
        field: dict[str, Any],
        *,
        preserve_confirmed: bool = True,
    ) -> bool:
        """计算字段状态；返回字段是否被本次复验重新计算。"""
        if preserve_confirmed and field.get("状态") in {STATE_PASSED, STATE_UNCHANGED} \
                and field.get("采用版本"):
            return False

        if field.get("变更类型") == "未变更" or field.get("新版本") == field.get("原版本"):
            field["状态"] = STATE_UNCHANGED
            field["采用版本"] = field["原版本"]
            field["生效规则"] = copy.deepcopy(field["原规则"])
            field["是否采用新版"] = False
            field["缺列"] = []
            field["缺列来源"] = []
        else:
            missing = self._missing_columns(field, batch.get("来源列") or {})
            if missing:
                # 依赖缺失：保留缺列来源和原规则，绝不采用本次尚未通过的新版。
                field["状态"] = STATE_PENDING
                field["采用版本"] = field["原版本"]
                field["生效规则"] = copy.deepcopy(field["原规则"])
                field["是否采用新版"] = False
                field["缺列"] = missing
                field["缺列来源"] = [field["来源"]]
            else:
                field["状态"] = STATE_PASSED
                field["采用版本"] = field["新版本"]
                field["生效规则"] = copy.deepcopy(field["新规则"])
                field["是否采用新版"] = True
                field["缺列"] = []
                field["缺列来源"] = []
        field["映射版本"] = field["采用版本"]
        field["目标字段"] = (field["生效规则"] or {}).get("目标字段") or field["校验字段"]
        return True

    def _evaluate_batch(self, batch: dict[str, Any], *, preserve_confirmed: bool) -> list[dict[str, Any]]:
        touched: list[dict[str, Any]] = []
        for field in batch["字段"]:
            if self._evaluate_field(batch, field, preserve_confirmed=preserve_confirmed):
                touched.append(field)
        return touched

    def _refresh_batch_status(self, batch: dict[str, Any]) -> None:
        states = {field["状态"] for field in batch["字段"]}
        if STATE_PENDING in states:
            batch["状态"] = BATCH_PENDING
        elif states and states <= {STATE_PASSED, STATE_UNCHANGED}:
            batch["状态"] = BATCH_DONE
        elif states == {STATE_WAIT}:
            batch["状态"] = BATCH_RUNNING
        else:
            batch["状态"] = BATCH_RUNNING

    @staticmethod
    def _state_counts(batch: dict[str, Any]) -> dict[str, int]:
        counts = {state: 0 for state in FIELD_STATES}
        for field in batch["字段"]:
            if field["状态"] in counts:
                counts[field["状态"]] += 1
        return counts

    def _append_round(self, batch: dict[str, Any], action: str, *, 说明: str = "",
                      extra: dict[str, Any] | None = None) -> dict[str, Any]:
        round_entry = {
            "轮次": len(batch["复验记录"]) + 1,
            "动作": action,
            "时间": _now(),
            "说明": 说明,
            "状态统计": self._state_counts(batch),
            "字段": [self._field_snapshot(field) for field in batch["字段"]],
            "生效范围": self._scope(batch),
        }
        if extra:
            round_entry.update(extra)
        batch["复验记录"].append(round_entry)
        return round_entry

    @staticmethod
    def _field_snapshot(field: dict[str, Any]) -> dict[str, Any]:
        return {
            "来源": field["来源"],
            "校验字段": field["校验字段"],
            "规则标识": field["规则标识"],
            "状态": field["状态"],
            "采用版本": field["采用版本"],
            "原版本": field["原版本"],
            "新版本": field["新版本"],
            "是否采用新版": field["是否采用新版"],
            "目标字段": field["目标字段"],
            "映射版本": field["映射版本"],
            "受影响列": list(field.get("受影响列") or []),
            "上游依赖": list(field.get("上游依赖") or []),
            "缺列": list(field.get("缺列") or []),
            "缺列来源": list(field.get("缺列来源") or []),
        }

    def revalidate(self, ref: Any) -> dict[str, Any] | None:
        """再次执行整组复验；已确认的字段保持已采用的版本。"""
        batch = self.find_batch(ref)
        if batch is None:
            return None
        touched = self._evaluate_batch(batch, preserve_confirmed=True)
        self._refresh_batch_status(batch)
        self._append_round(
            batch,
            "整组复验",
            说明="重复提交，已确认字段保持原采用版本",
            extra={"复算字段": [field["字段标识"] for field in touched]},
        )
        return self._detail(batch, alias=True)

    def submit(self, ref: Any, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """提交复验结果；语义与整组复验一致且幂等。"""
        return self.revalidate(ref)

    def resume(self, ref: Any, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """补列后续做：只重算受补列影响的字段，其余已确认字段不动。"""
        batch = self.find_batch(ref)
        if batch is None:
            return None
        payload = payload or {}
        supplies = (
            payload.get("补列")
            or payload.get("supplements")
            or payload.get("补充列")
            or []
        )
        if isinstance(supplies, dict):
            supplies = [supplies]

        added: list[dict[str, Any]] = []

        def _add(source: str, columns: list[Any]) -> None:
            batch["来源列"].setdefault(source, [])
            fresh = []
            for column in columns:
                column = str(column)
                if column and column not in batch["来源列"][source]:
                    batch["来源列"][source].append(column)
                    fresh.append(column)
            if fresh:
                for item in added:
                    if item["来源"] == source:
                        item["列"].extend(fresh)
                        break
                else:
                    added.append({"来源": source, "列": fresh})

        for item in supplies:
            if isinstance(item, str):
                source = str(payload.get("来源") or payload.get("source") or "")
                columns = [item]
            else:
                source = str(item.get("来源") or item.get("source") or payload.get("来源") or "")
                columns = item.get("列") or item.get("columns") or item.get("column") or []
                if isinstance(columns, str):
                    columns = [columns]
            if not source:
                raise ValueError("补列缺少「来源」")
            if not columns:
                continue
            _add(source, columns)

        # 兼容只传来源和列名的简写。
        simple_source = payload.get("来源") or payload.get("source")
        simple_columns = payload.get("列") or payload.get("columns")
        if simple_source and simple_columns and not supplies:
            if isinstance(simple_columns, str):
                simple_columns = [simple_columns]
            _add(str(simple_source), simple_columns)

        if not added:
            raise ValueError("请提供要补全的列")

        added_columns = {column for item in added for column in item["列"]}
        added_sources = {item["来源"] for item in added}
        touched: list[dict[str, Any]] = []
        for field in batch["字段"]:
            if field.get("状态") not in {STATE_PENDING, STATE_WAIT}:
                # 已确认的字段不因补列而换版本。
                continue
            if field["来源"] not in added_sources:
                continue
            dependencies = set(field.get("上游依赖") or []) | set(
                (field.get("新规则") or {}).get("依赖列") or [])
            dependencies.add(str((field.get("新规则") or {}).get("来源列") or ""))
            if not dependencies & added_columns:
                continue
            if self._missing_columns(field, batch["来源列"]):
                continue
            self._evaluate_field(batch, field, preserve_confirmed=False)
            touched.append(field)

        self._refresh_batch_status(batch)
        self._append_round(
            batch,
            "补列续做",
            说明="仅续做受补列影响的字段",
            extra={
                "补列": added,
                "续做字段": [field["字段标识"] for field in touched],
            },
        )
        return self._detail(batch, alias=True)

    # ------------------------------------------------------------ 生效范围 / 试跑
    def _scope(self, batch: dict[str, Any], sources: list[str] | None = None) -> dict[str, Any]:
        selected = set(sources or batch["来源"])
        fields = [field for field in batch["字段"] if field["来源"] in selected]
        versions: dict[str, dict[str, str]] = {}
        adopted: dict[str, str] = {}
        mapping_versions: dict[str, str] = {}
        pending_columns: dict[str, list[str]] = {}
        detail: list[dict[str, Any]] = []
        for field in fields:
            versions.setdefault(field["来源"], {})[field["校验字段"]] = field["采用版本"]
            adopted[field["字段标识"]] = field["采用版本"]
            mapping_versions[field["目标字段"]] = field["映射版本"]
            if field.get("缺列"):
                pending_columns.setdefault(field["来源"], [])
                for column in field["缺列"]:
                    if column not in pending_columns[field["来源"]]:
                        pending_columns[field["来源"]].append(column)
            detail.append({
                "来源": field["来源"],
                "校验字段": field["校验字段"],
                "规则标识": field["规则标识"],
                "状态": field["状态"],
                "采用版本": field["采用版本"],
                "原版本": field["原版本"],
                "新版本": field["新版本"],
                "是否采用新版": field["是否采用新版"],
                "目标字段": field["目标字段"],
                "映射版本": field["映射版本"],
                "缺列": list(field.get("缺列") or []),
                "缺列来源": list(field.get("缺列来源") or []),
            })
        return {
            "批次标识": batch["批次标识"],
            "状态": batch["状态"],
            "来源": [source for source in batch["来源"] if source in selected],
            "版本汇总": versions,
            "采用版本明细": adopted,
            "映射版本": mapping_versions,
            "待补列": pending_columns,
            "字段版本": detail,
        }

    def effective_scope(self, ref: Any, sources: list[str] | None = None) -> dict[str, Any] | None:
        batch = self.find_batch(ref)
        if batch is None:
            return None
        return self._scope(batch, sources)

    @staticmethod
    def _apply_mapping(rule: dict[str, Any], sample: dict[str, Any]) -> Any:
        column = str(rule.get("来源列") or "")
        default = rule.get("默认取值", "")
        value = sample.get(column, default)
        transform = str(rule.get("转换函数") or "")
        if transform == "upper":
            return str(value).upper()
        if transform == "lower":
            return str(value).lower()
        if transform == "int":
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return 0
        if transform == "trim":
            return str(value).strip()
        return value

    def dry_run(
        self,
        ref: Any,
        *,
        sources: list[str] | None = None,
        sample_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """按批次实际通过的规则版本运行试跑。"""
        batch = self.find_batch(ref)
        if batch is None:
            return None
        sample_data = sample_data or {}
        selected = [source for source in batch["来源"] if not sources or source in sources]
        fields = [field for field in batch["字段"] if field["来源"] in selected]
        results: list[dict[str, Any]] = []
        mapping: dict[str, Any] = {}
        for field in fields:
            source_sample = sample_data.get(field["来源"], sample_data)
            if not isinstance(source_sample, dict):
                source_sample = {}
            rule = field.get("生效规则") or field["原规则"]
            value = self._apply_mapping(rule, source_sample)
            mapping[field["目标字段"]] = value
            results.append({
                "来源": field["来源"],
                "校验字段": field["校验字段"],
                "规则标识": field["规则标识"],
                "状态": field["状态"],
                "采用版本": field["采用版本"],
                "映射版本": field["映射版本"],
                "原版本": field["原版本"],
                "新版本": field["新版本"],
                "是否采用新版": field["是否采用新版"],
                "目标字段": field["目标字段"],
                "来源列": rule.get("来源列"),
                "映射值": value,
                "缺列": list(field.get("缺列") or []),
                "缺列来源": list(field.get("缺列来源") or []),
            })
        return {
            "批次": batch["id"],
            "批次标识": batch["批次标识"],
            "试跑来源": selected,
            "试跑字段": results,
            "映射值": mapping,
            "生效范围": self._scope(batch),
            "本次生效范围": self._scope(batch, selected),
        }

    # ------------------------------------------------------------ 详情
    def _grouping(self, batch: dict[str, Any]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for source in batch["来源"]:
            fields = [field for field in batch["字段"] if field["来源"] == source]
            counts = {state: 0 for state in FIELD_STATES}
            for field in fields:
                if field["状态"] in counts:
                    counts[field["状态"]] += 1
            groups.append({
                "来源": source,
                "字段数": len(fields),
                "状态统计": counts,
                "字段": [field["校验字段"] for field in fields],
            })
        return groups

    def _detail(
        self,
        batch: dict[str, Any],
        *,
        state: str | None = None,
        alias: bool = False,
    ) -> dict[str, Any]:
        fields = batch["字段"]
        if state and state not in {"全部", "all"}:
            fields = [field for field in fields if field["状态"] == state]
        detail = {
            "id": batch["id"],
            "批次标识": batch["批次标识"],
            "申请标识": batch["申请标识"],
            "状态": batch["状态"],
            "创建时间": batch["创建时间"],
            "来源": list(batch["来源"]),
            "来源列": copy.deepcopy(batch["来源列"]),
            "字段": copy.deepcopy(fields),
            "全部字段": copy.deepcopy(batch["字段"]),
            "状态统计": self._state_counts(batch),
            "分组": self._grouping(batch),
            "生效范围": self._scope(batch),
            "复验记录": copy.deepcopy(batch["复验记录"]),
            "规则行": copy.deepcopy(batch["规则行"]),
        }
        if alias:
            detail["batch_id"] = batch["批次标识"]
            detail["effective_scope"] = detail["生效范围"]
            detail["fields"] = detail["全部字段"]
        return detail

    def get_round(self, ref: Any, round_no: int) -> dict[str, Any] | None:
        batch = self.find_batch(ref)
        if batch is None:
            return None
        for entry in batch["复验记录"]:
            if int(entry["轮次"]) == round_no:
                return copy.deepcopy(entry)
        return None


# 单例：批次详情、字段映射试跑和路由共用同一份仓储，确保读到的生效范围一致。
revalidation_service = FieldRevalidationService()
