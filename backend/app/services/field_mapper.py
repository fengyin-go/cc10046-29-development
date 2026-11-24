"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService


class FieldMapperService(BaseModuleService):
    MODULE = "field_mapper"
    ENTITY = "映射方案"
    OPERATION_TERM = "转换"
    LIST_FIELDS = ["方案标识", "来源字段", "目标字段", "转换函数", "默认取值", "映射版本", "适用站点", "依赖字段"]
    REQUIRED_FIELDS = ["方案标识", "来源字段", "目标字段"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "启用映射": "已生效", "停用映射": "已停用"}
    NEGATIVE_ACTIONS = ["停用映射"]

    def domain_map_fields(self, source_data: dict, mapping_rules: list[dict]) -> dict:
        """根据映射规则将来源字段转换为目标字段。"""
        result: dict = {}
        for rule in mapping_rules:
            src_field = rule.get("source", "")
            tgt_field = rule.get("target", "")
            default = rule.get("default", "")
            transform = rule.get("transform", "")

            value = source_data.get(src_field, default)
            if transform == "upper":
                value = str(value).upper()
            elif transform == "lower":
                value = str(value).lower()
            elif transform == "int":
                try:
                    value = int(float(value))
                except (ValueError, TypeError):
                    value = 0
            result[tgt_field] = value
        return result

    def domain_map_revalidation_batch(
        self,
        batch_ref: Any,
        sources: list[str] | None = None,
        sample_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """读取字段复验批次实际通过的规则版本运行字段映射试跑。

        批次详情页和字段映射试跑都从同一个复验仓储取生效范围，
        因此两边看到的版本、映射值和待补字段完全一致。
        """
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.dry_run(
            batch_ref, sources=sources, sample_data=sample_data or {})

    def effective_scope_for_batch(
        self,
        batch_ref: Any,
        sources: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """与复验批次详情页同源的生效范围查询。"""
        from app.services.field_revalidation import revalidation_service

        return revalidation_service.effective_scope(batch_ref, sources)
