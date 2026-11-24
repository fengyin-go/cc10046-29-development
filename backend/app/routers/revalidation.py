"""字段复验批次接口：规则行选择、成批复验、补列续做、字段筛选和试跑。

固定路径必须在通用资源路由 `/api/{module}` 之前注册，否则会被动态段抢先匹配。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.data_validator import DataValidatorService
from app.services.field_mapper import FieldMapperService
from app.services.field_revalidation import revalidation_service

router = APIRouter(prefix="/api", tags=["字段复验"])

_mapper = FieldMapperService()
_validator = DataValidatorService()


def _require_batch(ref: str) -> dict[str, Any]:
    batch = revalidation_service.find_batch(ref)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"字段复验批次 {ref} 不存在")
    return batch


@router.get("/field-revalidation/rules", response_model=dict)
def list_rule_rows(
    source: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict[str, Any]:
    """可编入复验批次的字段校验规则行（跨来源）。"""
    rows = revalidation_service.list_rule_rows(source=source, keyword=keyword)
    sources: list[str] = []
    for row in rows:
        if row["来源"] not in sources:
            sources.append(row["来源"])
    return {"items": rows, "total": len(rows), "sources": sources}


@router.get("/field-revalidation/batches", response_model=dict)
def list_batches(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    items, total = revalidation_service.list_batches(
        status=status, source=source, page=page, size=size)
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/field-revalidation/batches", response_model=dict)
def create_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """把多个来源的规则行编入一个复验批次并立即成组复验。"""
    try:
        return _validator.domain_batch_revalidate(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/field-revalidation/batches/{batch_ref}", response_model=dict)
def get_batch(
    batch_ref: str,
    state: str | None = Query(default=None, description="待补 / 已通过 / 未受影响 / 全部"),
) -> dict[str, Any]:
    """批次详情；state 用于只筛出某一类字段。"""
    _require_batch(batch_ref)
    detail = _validator.domain_batch_detail(batch_ref, state=state)
    assert detail is not None
    return detail


@router.post("/field-revalidation/batches/{batch_ref}/revalidate", response_model=dict)
def revalidate_batch(batch_ref: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """重新执行整组复验：已确认字段不换版本。"""
    _require_batch(batch_ref)
    detail = revalidation_service.revalidate(batch_ref)
    assert detail is not None
    return detail


@router.post("/field-revalidation/batches/{batch_ref}/submit", response_model=dict)
def submit_batch(batch_ref: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """提交复验结果；对同一批次重复提交保持幂等。"""
    _require_batch(batch_ref)
    detail = _validator.domain_submit_batch(batch_ref, payload)
    assert detail is not None
    return detail


@router.post("/field-revalidation/batches/{batch_ref}/resume", response_model=dict)
def resume_batch(batch_ref: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """补列后续做：只重算受补列影响的字段。"""
    _require_batch(batch_ref)
    try:
        detail = _validator.domain_resume_batch(batch_ref, payload or {})
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    assert detail is not None
    return detail


@router.get("/field-revalidation/batches/{batch_ref}/scope", response_model=dict)
def batch_scope(
    batch_ref: str,
    sources: str | None = Query(default=None, description="逗号分隔的来源列表"),
) -> dict[str, Any]:
    """批次实际生效范围。"""
    _require_batch(batch_ref)
    selected = [item for item in (sources or "").split(",") if item]
    scope = _validator.domain_effective_scope(batch_ref, selected or None)
    assert scope is not None
    return scope


@router.get("/field-revalidation/batches/{batch_ref}/rounds/{round_no}", response_model=dict)
def get_round(batch_ref: str, round_no: int) -> dict[str, Any]:
    """回看某一轮复验当时筛出的字段和采用的版本。"""
    _require_batch(batch_ref)
    entry = revalidation_service.get_round(batch_ref, round_no)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"批次 {batch_ref} 没有第 {round_no} 轮复验记录")
    return entry


@router.post("/field-revalidation/batches/{batch_ref}/dry-run", response_model=dict)
def dry_run_batch(batch_ref: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """按批次实际通过的规则版本，对选定同组来源运行试跑。"""
    _require_batch(batch_ref)
    payload = payload or {}
    sources = payload.get("来源") or payload.get("sources") or payload.get("试跑来源") or []
    if isinstance(sources, str):
        sources = [item for item in sources.split(",") if item]
    sample = payload.get("样例数据") or payload.get("sample_data") or payload.get("sample") or {}
    result = revalidation_service.dry_run(
        batch_ref, sources=sources or None, sample_data=sample)
    assert result is not None
    return result


@router.post("/field-mapper/dry-run", response_model=dict)
def field_mapper_dry_run(payload: dict[str, Any]) -> dict[str, Any]:
    """字段映射试跑：读取字段复验批次实际通过的规则版本与生效范围。"""
    batch_ref = (
        payload.get("批次标识") or payload.get("batch_id")
        or payload.get("批次") or payload.get("batch")
    )
    if batch_ref in (None, ""):
        raise HTTPException(status_code=400, detail="请提供字段复验批次")
    _require_batch(str(batch_ref))
    sources = payload.get("来源") or payload.get("sources") or []
    if isinstance(sources, str):
        sources = [item for item in sources.split(",") if item]
    sample = payload.get("样例数据") or payload.get("sample_data") or payload.get("sample") or {}
    result = _mapper.domain_map_revalidation_batch(str(batch_ref), sources or None, sample)
    assert result is not None
    result["chain"] = "field-mapping-dry-run"
    return result


@router.get("/field-mapper/scope", response_model=dict)
def field_mapper_scope(
    batch_ref: str = Query(alias="batch_id"),
    sources: str | None = Query(default=None),
) -> dict[str, Any]:
    """字段映射侧读取批次生效范围，与批次详情页同源。"""
    _require_batch(batch_ref)
    selected = [item for item in (sources or "").split(",") if item]
    scope = _mapper.effective_scope_for_batch(batch_ref, selected or None)
    assert scope is not None
    return scope
