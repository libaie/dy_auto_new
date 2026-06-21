from pathlib import Path

from scripts.check_chinese_comments import (
    CheckResult,
    check_files,
    has_chinese_module_comment,
    high_risk_comment_gaps,
)


def test_python_file_requires_chinese_module_docstring(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text('"""视频生产服务。"""\n\nVALUE = 1\n', encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text('"""Video production service."""\n\nVALUE = 1\n', encoding="utf-8")

    assert has_chinese_module_comment(good)
    assert not has_chinese_module_comment(bad)


def test_javascript_file_accepts_leading_chinese_comment(tmp_path: Path):
    good = tmp_path / "good.js"
    good.write_text("// 设备任务执行入口。\nexport const value = 1\n", encoding="utf-8")
    bad = tmp_path / "bad.js"
    bad.write_text("// task runner\nexport const value = 1\n", encoding="utf-8")

    assert has_chinese_module_comment(good)
    assert not has_chinese_module_comment(bad)


def test_vue_file_accepts_leading_chinese_html_comment(tmp_path: Path):
    good = tmp_path / "Good.vue"
    good.write_text("<!-- 生产控制台页面。 -->\n<template></template>\n", encoding="utf-8")

    assert has_chinese_module_comment(good)


def test_high_risk_line_requires_nearby_chinese_comment(tmp_path: Path):
    bad = tmp_path / "risk.py"
    bad.write_text("def run():\n    provider.submit()\n", encoding="utf-8")
    good = tmp_path / "ok.py"
    good.write_text(
        "def run():\n    # 提交 provider 前已完成预算和幂等校验。\n    provider.submit()\n",
        encoding="utf-8",
    )

    assert high_risk_comment_gaps(bad)
    assert high_risk_comment_gaps(good) == []


def test_database_query_is_not_high_risk_by_itself(tmp_path: Path):
    path = tmp_path / "read_model.py"
    path.write_text(
        "def load(db):\n    return db.query(User).filter(User.id == '1').first()\n",
        encoding="utf-8",
    )

    assert high_risk_comment_gaps(path) == []


def test_database_commit_is_not_high_risk_by_itself(tmp_path: Path):
    path = tmp_path / "write_model.py"
    path.write_text("def save(db):\n    db.commit()\n", encoding="utf-8")

    assert high_risk_comment_gaps(path) == []


def test_httpx_exception_and_timeout_config_are_not_high_risk(tmp_path: Path):
    path = tmp_path / "http_errors.py"
    path.write_text(
        "TIMEOUT = httpx.Timeout(60, connect=10)\n"
        "def handle():\n"
        "    try:\n"
        "        pass\n"
        "    except httpx.TimeoutException as exc:\n"
        "        raise exc\n",
        encoding="utf-8",
    )

    assert high_risk_comment_gaps(path) == []


def test_submit_function_definition_is_not_high_risk_until_called(tmp_path: Path):
    path = tmp_path / "provider_tools.py"
    path.write_text(
        "async def submit_image_generation(run_id: str, job_id: str):\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )

    assert high_risk_comment_gaps(path) == []


def test_check_files_reports_missing_module_comment(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text("VALUE = 1\n", encoding="utf-8")

    result = check_files([bad], strict_risk=False)

    assert result == CheckResult(module_missing=[bad], risk_missing=[])
