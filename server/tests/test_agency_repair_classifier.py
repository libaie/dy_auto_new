from app.services.agency_repair_classifier import classify_repair_tasks


def test_structured_storyboard_repair_is_auto_executable():
    result = classify_repair_tasks(
        {
            "repair_tasks": [{
                "type": "storyboard_missing_references",
                "stage": "storyboard",
                "target_type": "episode",
                "target_id": "episode-1",
                "series_id": "series-1",
                "auto_execute": True,
                "requires_paid_provider": False,
                "reason": "分镜缺少角色和场景参考",
                "expected_result": "补齐引用后重新进入审查",
            }],
        },
        stage="storyboard",
        series_id="series-1",
    )

    assert result.repairable is True
    assert result.manual_gate_required is True
    assert result.repair_tasks[0].repair_action_label == "去系列详情补分镜参考"


def test_generic_or_unreadable_finding_becomes_manual_required():
    result = classify_repair_tasks({"summary": "已记录审查发现"}, stage="style_lock", series_id="series-1")

    assert result.repairable is False
    assert result.manual_gate_required is True
    assert result.repair_tasks[0].reason == "专家审查结果缺少可执行结论，需要人工确认"
