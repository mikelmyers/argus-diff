"""argus-diff — geometric diff for mechanical CAD. git diff for atoms."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from argus_diff.diff import DiffResult, diff_files
from argus_diff.loader import BodyInfo, load_step

try:
    __version__ = _pkg_version("argus-diff")
except PackageNotFoundError:  # source tree without an installed dist
    __version__ = "0+unknown"
__all__ = ["BodyInfo", "DiffResult", "diff_files", "load_step", "__version__"]
