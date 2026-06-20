import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    ContentTemplate as LegacyContentTemplate,
    DMSequence as LegacyDMSequence,
    RepliedComment as LegacyRepliedComment,
    SensitiveWord as LegacySensitiveWord,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_content_collection_model_boundary_reexports_template_and_sensitive_word():
    from app.db.models.content_collection import ContentTemplate, DMSequence, RepliedComment, SensitiveWord

    assert ContentTemplate is LegacyContentTemplate
    assert DMSequence is LegacyDMSequence
    assert RepliedComment is LegacyRepliedComment
    assert SensitiveWord is LegacySensitiveWord
    assert ContentTemplate.metadata is Base.metadata
    assert DMSequence.metadata is Base.metadata
    assert RepliedComment.metadata is Base.metadata
    assert SensitiveWord.metadata is Base.metadata
    assert "content_templates" in Base.metadata.tables
    assert "dm_sequences" in Base.metadata.tables
    assert "replied_comments" in Base.metadata.tables
    assert "sensitive_words" in Base.metadata.tables


def test_content_collection_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.content_collection import ContentTemplate, DMSequence, RepliedComment, SensitiveWord; "
        "assert legacy.ContentTemplate is ContentTemplate; "
        "assert legacy.DMSequence is DMSequence; "
        "assert legacy.RepliedComment is RepliedComment; "
        "assert legacy.SensitiveWord is SensitiveWord"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
