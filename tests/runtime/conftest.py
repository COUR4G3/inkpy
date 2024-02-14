import pytest

from inkpy.runtime.exceptions import StoryException
from inkpy.runtime.story import Story


@pytest.fixture(scope="module")
def compile_story(testdir):
    def _compile_story(name):
        with open(testdir / f"{name}.ink.json", "r", encoding="utf-8-sig") as f:
            story = Story(f)

        @story.on_error
        def on_error(message):
            raise StoryException(message)

        return story

    return _compile_story
