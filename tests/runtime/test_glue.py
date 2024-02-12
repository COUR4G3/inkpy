import pytest

from inkpy.runtime.story import Story


def test_implicit_inline_a(datadir):
    with open(
        datadir / "glue" / "implicit_inline_a.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "I have five eggs.\n"


def test_implicit_inline_b(datadir):
    with open(
        datadir / "glue" / "implicit_inline_b.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "A\nX\n"



def test_implicit_inline_c(datadir):
    with open(
        datadir / "glue" / "implicit_inline_c.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "A\nC\n"


def test_left_right_matching(datadir):
    with open(
        datadir / "glue" / "left_right_matching.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "A line.\nAnother line.\n"


def test_simple(datadir):
    with open(
        datadir / "glue" / "simple.ink.json", "r", encoding="utf-8-sig"
    ) as f:
        story = Story(f)

    assert story.continue_() == "Some content with glue.\n"
