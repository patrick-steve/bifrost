import pytest

from dn import scenario as sc


@pytest.fixture(scope="session")
def showcase():
    return sc.showcase()
