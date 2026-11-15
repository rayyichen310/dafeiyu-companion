"""Load the plugin package the way Hermes does (as a directory package), without Hermes itself."""
import importlib.util
import os
import sys
import types
from pathlib import Path

NAME = "dafeiyu_companion_under_test"


def _stub_hermes_constants(pkg_dir: Path) -> None:
    """Without Hermes on the path, stand in for hermes_constants: the home is HERMES_HOME or the
    home whose plugins/ directory holds this checkout."""
    try:
        import hermes_constants  # noqa: F401
        return
    except ImportError:
        pass
    stub = types.ModuleType("hermes_constants")
    stub.get_hermes_home = lambda: Path(os.environ.get("HERMES_HOME") or pkg_dir.parents[1])
    sys.modules["hermes_constants"] = stub


def load_plugin():
    if NAME in sys.modules:
        return sys.modules[NAME]
    pkg_dir = Path(__file__).resolve().parents[1]
    _stub_hermes_constants(pkg_dir)
    spec = importlib.util.spec_from_file_location(
        NAME, pkg_dir / "__init__.py", submodule_search_locations=[str(pkg_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = module
    spec.loader.exec_module(module)
    return module
