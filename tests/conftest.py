"""Keep generated test artefacts in the repository-local ignored cache."""

from pathlib import Path

from hypothesis import settings
from hypothesis.database import DirectoryBasedExampleDatabase

DATABASE = Path(__file__).resolve().parents[1] / ".cache" / "hypothesis_runtime"
settings.register_profile("rwa_project", database=DirectoryBasedExampleDatabase(DATABASE))
settings.load_profile("rwa_project")
