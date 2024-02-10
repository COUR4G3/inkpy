import pytest

from inkpy.runtime.story import Story


def test_hello_world(datadir):
    with (datadir / "hello_world.ink.json").open("r", encoding="utf-8-sig") as f:
        story = Story(f)

    assert story.continue_() == "hello world"
    assert story.can_continue is False
