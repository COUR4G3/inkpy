import pytest

from inkpy.runtime.story import Story


@pytest.fixture(scope="module")
def compile_story(testdir):
    def _compile_story(name):
        with open(testdir / f"{name}.ink.json", "r", encoding="utf-8-sig") as f:
            return Story(f)

    return _compile_story
