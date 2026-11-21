"""The root conftest must give this project its own tools/ modules, not the other project's."""

from pathlib import Path

import common
import validate


def test_common_is_this_projects():
    assert Path(common.__file__).parent.parent.name == "gear"


def test_validate_is_this_projects():
    assert Path(validate.__file__).parent.parent.name == "gear"


def test_runtime_import_resolves_to_this_project():
    import common as again

    assert again is common
