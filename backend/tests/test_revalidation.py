"""字段复验批次：成组复验、补列续做、版本锁定与试跑一致性。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import HTTPException

from app.routers.revalidation import (
    create_batch,
    dry_run_batch,
    get_batch,
    get_round,
    list_rule_rows,
    revalidate_batch,
    resume_batch,
    submit_batch,
    field_mapper_dry_run,
    field_mapper_scope,
    batch_scope,
)
from app.services.field_mapper import FieldMapperService
from app.services.field_revalidation import (
    FieldRevalidationService,
    STATE_PASSED,
    STATE_PENDING,
    STATE_UNCHANGED,
)


def _service() -> FieldRevalidationService:
    return FieldRevalidationService()


def _field(detail, source):
    return next(field for field in detail["全部字段"] if field["来源"] == source)


def test_rule_rows_cover_three_sources():
    service = _service()
    rows = service.list_rule_rows()
    assert {row["来源"] for row in rows} == {"甲", "乙", "丙"}


def test_create_batch_mixed_states():
    detail = _service().create_batch({"规则行": [1, 2, 3]})
    assert detail["状态"] == "待补"
    assert detail["来源"] == ["甲", "乙", "丙"]
    assert _field(detail, "甲")["状态"] == STATE_PASSED
    assert _field(detail, "乙")["状态"] == STATE_PENDING
    assert _field(detail, "丙")["状态"] == STATE_UNCHANGED
    assert detail["状态统计"] == {"待补": 1, "已通过": 1, "未受影响": 1}


def test_pending_keeps_old_version_and_missing_source():
    detail = _service().create_batch({"规则行": [1, 2, 3]})
    yi = _field(detail, "乙")
    assert yi["采用版本"] == "v1"
    assert yi["是否采用新版"] is False
    assert yi["缺列"] == ["基价"]
    assert yi["缺列来源"] == ["乙"]
    assert yi["生效规则"]["版本"] == "v1"


def test_unchanged_source_keeps_old_version():
    detail = _service().create_batch({"规则行": [1, 2, 3]})
    bing = _field(detail, "丙")
    assert bing["采用版本"] == "v1"
    assert bing["是否采用新版"] is False
    assert bing["受影响列"] == []


def test_dry_run_does_not_show_pending_as_new_version():
    service = _service()
    detail = service.create_batch({"规则行": [1, 2, 3]})
    result = service.dry_run(detail["批次标识"], sources=["甲", "乙"])
    by_source = {item["来源"]: item for item in result["试跑字段"]}
    assert by_source["甲"]["采用版本"] == "v2"
    assert by_source["甲"]["映射版本"] == "v2"
    assert by_source["乙"]["采用版本"] == "v1"
    assert by_source["乙"]["是否采用新版"] is False
    assert by_source["乙"]["映射版本"] != "v2"


def test_dry_run_uses_passed_rule_and_mapping_values():
    service = _service()
    detail = service.create_batch({"规则行": [1, 2, 3]})
    result = service.dry_run(
        detail["批次标识"],
        sources=["甲", "乙"],
        sample_data={"甲": {"商品名称": "旧名称", "新名称列": "新名称"},
                     "乙": {"价格": "12", "基价": "18"}},
    )
    by_source = {item["来源"]: item for item in result["试跑字段"]}
    assert by_source["甲"]["来源列"] == "新名称列"
    assert by_source["甲"]["映射值"] == "新名称"
    assert by_source["乙"]["来源列"] == "价格"
    assert by_source["乙"]["映射值"] == 12
    assert result["映射值"] == {"product_name": "新名称", "settlement_price": 12}


def test_two_scope_reads_stay_consistent():
    detail = create_batch({"规则行": [1, 2, 3]})
    batch_ref = detail["批次标识"]
    left = batch_scope(batch_ref, "甲,乙")
    mapper = FieldMapperService()
    right = mapper.effective_scope_for_batch(batch_ref, ["甲", "乙"])
    assert left == right
    assert left["采用版本明细"]
    assert left["版本汇总"]["甲"]["商品名称"] == "v2"
    assert left["版本汇总"]["乙"]["结算价"] == "v1"


def test_resume_only_touches_affected_fields():
    service = _service()
    detail = service.create_batch({"规则行": [1, 2, 3]})
    batch_ref = detail["批次标识"]
    jia_before = _field(detail, "甲")["采用版本"]
    result = service.resume(batch_ref, {"补列": [{"来源": "乙", "列": ["基价"]}]})
    assert _field(result, "乙")["状态"] == STATE_PASSED
    assert _field(result, "乙")["采用版本"] == "v2"
    assert _field(result, "甲")["采用版本"] == jia_before
    assert _field(result, "丙")["状态"] == STATE_UNCHANGED
    latest = result["复验记录"][-1]
    assert latest["动作"] == "补列续做"
    assert latest["补列"] == [{"来源": "乙", "列": ["基价"]}]

def test_repeated_submit_keeps_confirmed_versions():
    service = _service()
    detail = service.create_batch({"规则行": [1, 2, 3]})
    batch_ref = detail["批次标识"]
    service.resume(batch_ref, {"补列": [{"来源": "乙", "列": ["基价"]}]})
    first = service.submit(batch_ref)
    second = service.submit(batch_ref)
    versions_first = {f["来源"]: f["采用版本"] for f in first["全部字段"]}
    versions_second = {f["来源"]: f["采用版本"] for f in second["全部字段"]}
    assert versions_first == versions_second
    assert versions_second["甲"] == "v2"
    assert versions_second["乙"] == "v2"
    assert versions_second["丙"] == "v1"


def test_round_snapshot_keeps_historical_result():
    service = _service()
    detail = service.create_batch({"规则行": [1, 2, 3]})
    batch_ref = detail["批次标识"]
    service.resume(batch_ref, {"补列": [{"来源": "乙", "列": ["基价"]}]})
    round_one = service.get_round(batch_ref, 1)
    assert round_one["状态统计"] == {"待补": 1, "已通过": 1, "未受影响": 1}
    yi = next(item for item in round_one["字段"] if item["来源"] == "乙")
    assert yi["状态"] == STATE_PENDING
    assert yi["采用版本"] == "v1"
    # 当前批次已经补列通过，历史轮次仍保留当时结果。
    assert _field(service.get_batch(batch_ref), "乙")["采用版本"] == "v2"


def test_state_filter_on_detail():
    service = _service()
    detail = service.create_batch({"规则行": [1, 2, 3]})
    pending = service.get_batch(detail["批次标识"], state="待补")
    assert [field["来源"] for field in pending["字段"]] == ["乙"]
    passed = service.get_batch(detail["批次标识"], state="已通过")
    assert [field["来源"] for field in passed["字段"]] == ["甲"]
    untouched = service.get_batch(detail["批次标识"], state="未受影响")
    assert [field["来源"] for field in untouched["字段"]] == ["丙"]


def test_missing_column_scenario_can_be_simulated():
    service = _service()
    detail = service.create_batch({
        "规则行": [1, 2, 3],
        "来源列": {"乙": ["结算价"]},
    })
    assert _field(detail, "乙")["状态"] == STATE_PENDING
    assert _field(detail, "乙")["缺列"] == ["基价"]


def test_http_create_and_dry_run_endpoints():
    payload = create_batch({"规则行": [1, 2, 3], "申请标识": "APP-HTTP-1"})
    batch_ref = payload["批次标识"]
    detail = get_batch(batch_ref, state="待补")
    assert [field["来源"] for field in detail["字段"]] == ["乙"]
    result = dry_run_batch(batch_ref, {"来源": ["甲", "乙"], "样例数据": {}})
    assert result["试跑来源"] == ["甲", "乙"]
    scope = batch_scope(batch_ref, "甲,乙")
    assert scope["版本汇总"]["乙"]["结算价"] == "v1"
    mapper_result = field_mapper_dry_run({"批次标识": batch_ref, "来源": ["甲", "乙"]})
    assert mapper_result["chain"] == "field-mapping-dry-run"
    assert mapper_result["本次生效范围"] == result["本次生效范围"]
    assert field_mapper_scope(batch_ref, "甲,乙") == scope


def test_http_rejects_unknown_batch():
    with pytest.raises(HTTPException):
        get_batch("FRB-不存在")


def test_data_validator_domain_batch_methods():
    from app.services.data_validator import DataValidatorService

    validator = DataValidatorService()
    detail = validator.domain_batch_revalidate({"规则行": [1, 2, 3]})
    batch_ref = detail["批次标识"]
    assert validator.domain_batch_detail(batch_ref, state="待补")["字段"][0]["来源"] == "乙"
    assert validator.domain_effective_scope(batch_ref)["版本汇总"]["甲"]["商品名称"] == "v2"
    resumed = validator.domain_resume_batch(batch_ref, {"补列": [{"来源": "乙", "列": ["基价"]}]})
    assert resumed["状态统计"]["待补"] == 0
    submitted = validator.domain_submit_batch(batch_ref)
    assert submitted["生效范围"]["采用版本明细"]["乙-结算价"] == "v2"
