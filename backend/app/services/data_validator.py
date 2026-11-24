"""数据校验器领域服务：单条规则维护 + 字段校验样本的批量复验。

单条规则的状态流转仍走基类；批量复验把多个来源的规则行编成字段复验批次，
逐条记录实际受影响的列与上游依赖，并把实际通过的版本交给字段映射试跑复用。
"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService


class DataValidatorService(BaseModuleService):
    MODULE = "data_validator"
    ENTITY = "校验规则"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["规则标识", "校验字段", "校验类型", "校验参数", "失败动作", "阻断阈值", "采样比例", "上次执行"]
    REQUIRED_FIELDS = ["规则标识", "校验字段", "校验类型"]
    STATUS_ORDER = ["草稿", "待校验", "已启用", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "启用规则": "已启用", "停用规则": "已停用"}
    NEGATIVE_ACTIONS = ["停用规则"]

    def domain_batch_revalidate(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """字段校验样本的批量校验：把选中的规则行成组复验。

        与单条规则动作不同，这里返回的是一个批次详情：
        每个字段带状态（待补 / 已通过 / 未受影响）、受影响列、上游依赖、采用版本。
        """
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.create_batch(payload or {})

    def domain_batch_detail(
        self,
        batch_ref: Any,
        state: str | None = None,
    ) -> dict[str, Any] | None:
        """按待补 / 已通过 / 未受影响筛选批次字段。"""
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.get_batch(batch_ref, state=state)

    def domain_resume_batch(
        self,
        batch_ref: Any,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """补列后续做：只续做受补列影响的字段。"""
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.resume(batch_ref, payload or {})

    def domain_submit_batch(
        self,
        batch_ref: Any,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """提交复验结果；同一批次重复提交是幂等的。"""
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.submit(batch_ref, payload)

    def domain_effective_scope(
        self,
        batch_ref: Any,
        sources: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """批次实际生效范围；字段映射试跑读取同一份结果。"""
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.effective_scope(batch_ref, sources)
