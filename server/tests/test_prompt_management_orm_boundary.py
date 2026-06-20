import subprocess
import sys
from pathlib import Path

from app.db.models import Base, PromptTemplate as LegacyPromptTemplate


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_prompt_management_model_boundary_reexports_prompt_template():
    from app.db.models.prompt_management import PromptTemplate

    assert PromptTemplate is LegacyPromptTemplate
    assert PromptTemplate.metadata is Base.metadata
    assert "prompt_templates" in Base.metadata.tables


def test_prompt_management_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.prompt_management import PromptTemplate; "
        "assert legacy.PromptTemplate is PromptTemplate; "
        "assert 'prompt_templates' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
