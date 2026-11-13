"""Load the plugin package the way Hermes does (as a directory package), without Hermes itself."""
import importlib.util
import sys
from pathlib import Path

NAME = "dafeiyu_companion_under_test"


def load_plugin():
    if NAME in sys.modules:
        return sys.modules[NAME]
    pkg_dir = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        NAME, pkg_dir / "__init__.py", submodule_search_locations=[str(pkg_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = module
    spec.loader.exec_module(module)
    return module
