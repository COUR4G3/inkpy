import pytest

from inkpy.runtime.story import Story


def test_minimal(datadir):
    with (datadir / "minimal.ink.json").open("r", encoding="utf-8-sig") as f:
        story = Story(f)

    story.continue_()
    assert story.can_continue is False
