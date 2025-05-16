"""Test the version endpoint of the SCR API."""
import re
from ..scr.endpoints import version


def test_get_version():
    """
    Test the get_version function to ensure it returns a valid version string.
    """


regex = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

version = version.get_version()
assert re.match(regex, version) is not None
