import pytest

from inkpy.runtime.story import Story


def test_simple(datadir):
    with open(datadir / "content" / "simple.ink.json", "r", encoding="utf-8-sig") as f:
        story = Story(f)

    assert story.continue_() == "hello world\n"
    assert story.can_continue is False


def test_multiline(datadir):
    with open(
        datadir / "content" / "multiline.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "first line\n"
    assert story.can_continue is True
    assert story.continue_() == "second line\n"
    assert story.can_continue is False


def test_glue_simple(datadir):
    with open(
        datadir / "content" / "glue_simple.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "Some content with glue.\n"
    assert story.can_continue is False
