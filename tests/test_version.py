from importlib.metadata import version

import turritopsis


def test_runtime_version_matches_installed_package_metadata():
    assert turritopsis.__version__ == version("turritopsis")
