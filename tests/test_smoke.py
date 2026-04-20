from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_APP = PROJECT_ROOT / "orchestrator" / "app"
sys.path.insert(0, str(ORCHESTRATOR_APP))

from pipeline import run_pipeline  # noqa: E402


def test_run_pipeline_smoke(capsys) -> None:
    run_pipeline("job-0001")
    captured = capsys.readouterr()

    assert "layout stage" in captured.out
    assert "ocr stage" in captured.out
    assert "assembly stage" in captured.out
