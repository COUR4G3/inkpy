import pytest

from .utils import load_and_continue


@pytest.mark.slow
def test_the_intercept():
    load_and_continue("the_intercept.ink.json")
