from pathlib import Path

from scripts.check_ai_video_report_coverage import (
    _known_repo_files,
    _pytest_ref_exists,
    _pytest_refs,
    _ref_exists,
    _report_ranges,
    _report_whole_file_refs,
    _reviewable_line_numbers,
    _report_file_refs,
    _source_line_coverage,
)


def test_report_checker_resolves_file_refs_and_pytest_nodes(tmp_path: Path):
    test_file = tmp_path / "server" / "tests" / "test_storyboard_image_service.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "def test_force_storyboard_frame_image_payload_uses_fresh_idempotency_key():\n"
        "    pass\n",
        encoding="utf-8",
    )
    frontend_file = tmp_path / "web" / "src" / "__tests__" / "video-production-run-type-api.test.js"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_text("test('run type', () => {})\n", encoding="utf-8")

    report = (
        "`test_storyboard_image_service.py::test_force_storyboard_frame_image_payload_uses_fresh_idempotency_key` "
        "`test_storyboard_image_service.py::test_force_storyboard_frame_image_*` "
        "`video-production-run-type-api.test.js`"
    )
    known_files = _known_repo_files(tmp_path)

    file_refs = _report_file_refs(report)
    assert "test_storyboard_image_service.py" in file_refs
    assert "video-production-run-type-api.test.js" in file_refs
    assert _ref_exists("video-production-run-type-api.test.js", known_files)
    assert not _ref_exists("missing.test.js", known_files)
    pytest_refs = _pytest_refs(report)
    assert (
        "test_storyboard_image_service.py",
        "test_force_storyboard_frame_image_payload_uses_fresh_idempotency_key",
    ) in pytest_refs
    assert ("test_storyboard_image_service.py", "test_force_storyboard_frame_image_*") in pytest_refs
    assert _pytest_ref_exists(
        tmp_path,
        known_files,
        "test_storyboard_image_service.py",
        "test_force_storyboard_frame_image_payload_uses_fresh_idempotency_key",
    )
    assert _pytest_ref_exists(
        tmp_path,
        known_files,
        "test_storyboard_image_service.py",
        "test_force_storyboard_frame_image_*",
    )
    assert not _pytest_ref_exists(
        tmp_path,
        known_files,
        "test_storyboard_image_service.py",
        "test_missing",
    )


def test_report_checker_counts_reviewable_source_lines(tmp_path: Path):
    path = tmp_path / "sample.py"
    path.write_text(
        "\n# ignored\nimport json\n\n\ndef run(*args):\n    return json.dumps(args)\n",
        encoding="utf-8",
    )

    assert _reviewable_line_numbers(path) == [6, 7]


def test_report_checker_does_not_treat_any_file_mention_as_whole_file(tmp_path: Path):
    root = tmp_path
    path = root / "server" / "scripts" / "check_ai_video_report_coverage.py"
    path.parent.mkdir(parents=True)
    path.write_text("import json\n\ndef run():\n    return json.dumps({'ok': True})\n", encoding="utf-8")
    files = [path]
    report = (
        "| 文件/行号 | 证据 |\n"
        "| --- | --- |\n"
        "| `server/scripts/check_ai_video_report_coverage.py`:4+ | "
        "`server/scripts/check_ai_video_report_coverage.py --report audit.md` |\n"
    )

    total, covered, missing = _source_line_coverage(
        files,
        _report_ranges(report, files, root),
        _report_whole_file_refs(report, files, root),
        root,
    )

    assert total == 2
    assert covered == 1
    assert missing == ["server/scripts/check_ai_video_report_coverage.py:3"]


def test_report_checker_applies_glob_line_ranges(tmp_path: Path):
    root = tmp_path
    path = root / "web" / "src" / "api" / "aiConfig.js"
    path.parent.mkdir(parents=True)
    path.write_text("export function listModels() {}\n", encoding="utf-8")
    files = [path]
    report = "| 文件/行号 | 证据 |\n| --- | --- |\n| `web/src/api/*.js`:1+ | checked |\n"

    total, covered, missing = _source_line_coverage(
        files,
        _report_ranges(report, files, root),
        _report_whole_file_refs(report, files, root),
        root,
    )

    assert (total, covered, missing) == (1, 1, [])
