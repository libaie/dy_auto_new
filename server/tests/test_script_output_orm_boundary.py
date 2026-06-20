import subprocess
import sys
from pathlib import Path

from app.db.models import Base
from app.db.models import EpisodeScript as LegacyEpisodeScript
from app.db.models import ScriptDramaticBeat as LegacyScriptDramaticBeat
from app.db.models import ScriptSceneOutline as LegacyScriptSceneOutline
from app.db.models import ScriptVisualShot as LegacyScriptVisualShot


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_script_pipeline_model_boundary_reexports_script_output_models():
    from app.db.models.script_pipeline import (
        EpisodeScript,
        ScriptDramaticBeat,
        ScriptSceneOutline,
        ScriptVisualShot,
    )

    assert EpisodeScript is LegacyEpisodeScript
    assert ScriptDramaticBeat is LegacyScriptDramaticBeat
    assert ScriptSceneOutline is LegacyScriptSceneOutline
    assert ScriptVisualShot is LegacyScriptVisualShot
    assert EpisodeScript.metadata is Base.metadata
    for table_name in (
        "episode_scripts",
        "script_dramatic_beats",
        "script_scene_outlines",
        "script_visual_shots",
    ):
        assert table_name in Base.metadata.tables


def test_script_pipeline_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.script_pipeline import EpisodeScript, ScriptDramaticBeat, ScriptSceneOutline, ScriptVisualShot; "
        "assert legacy.EpisodeScript is EpisodeScript; "
        "assert legacy.ScriptDramaticBeat is ScriptDramaticBeat; "
        "assert legacy.ScriptSceneOutline is ScriptSceneOutline; "
        "assert legacy.ScriptVisualShot is ScriptVisualShot; "
        "assert 'episode_scripts' in legacy.Base.metadata.tables; "
        "assert 'script_visual_shots' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
