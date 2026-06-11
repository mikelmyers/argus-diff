"""argus-diff — geometric diff for mechanical CAD. git diff for atoms."""

from argus_diff.diff import DiffResult, diff_files
from argus_diff.loader import BodyInfo, load_step

__version__ = "0.1.0"
__all__ = ["BodyInfo", "DiffResult", "diff_files", "load_step", "__version__"]
