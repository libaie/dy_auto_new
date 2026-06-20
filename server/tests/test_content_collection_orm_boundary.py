import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    CollectedComment as LegacyCollectedComment,
    CollectedUser as LegacyCollectedUser,
    ContentTemplate as LegacyContentTemplate,
    Conversation as LegacyConversation,
    DMSequence as LegacyDMSequence,
    RepliedComment as LegacyRepliedComment,
    SensitiveWord as LegacySensitiveWord,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_content_collection_model_boundary_reexports_template_and_sensitive_word():
    from app.db.models.content_collection import (
        CollectedComment,
        CollectedUser,
        ContentTemplate,
        Conversation,
        DMSequence,
        RepliedComment,
        SensitiveWord,
    )

    assert CollectedComment is LegacyCollectedComment
    assert CollectedUser is LegacyCollectedUser
    assert ContentTemplate is LegacyContentTemplate
    assert Conversation is LegacyConversation
    assert DMSequence is LegacyDMSequence
    assert RepliedComment is LegacyRepliedComment
    assert SensitiveWord is LegacySensitiveWord
    assert CollectedComment.metadata is Base.metadata
    assert CollectedUser.metadata is Base.metadata
    assert ContentTemplate.metadata is Base.metadata
    assert Conversation.metadata is Base.metadata
    assert DMSequence.metadata is Base.metadata
    assert RepliedComment.metadata is Base.metadata
    assert SensitiveWord.metadata is Base.metadata
    assert "collected_comments" in Base.metadata.tables
    assert "collected_users" in Base.metadata.tables
    assert "content_templates" in Base.metadata.tables
    assert "conversations" in Base.metadata.tables
    assert "dm_sequences" in Base.metadata.tables
    assert "replied_comments" in Base.metadata.tables
    assert "sensitive_words" in Base.metadata.tables


def test_content_collection_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.content_collection import CollectedComment, CollectedUser, ContentTemplate, Conversation, DMSequence, RepliedComment, SensitiveWord; "
        "assert legacy.CollectedComment is CollectedComment; "
        "assert legacy.CollectedUser is CollectedUser; "
        "assert legacy.ContentTemplate is ContentTemplate; "
        "assert legacy.Conversation is Conversation; "
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
