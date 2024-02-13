import pytest


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "glue"


def test_implicit_inline_a(compile_story):
    story = compile_story("implicit_inline_a")

    assert story.continue_() == "I have five eggs.\n"


# def test_implicit_inline_b(compile_story):
#     with open(testdir / "implicit_inline_b.ink.json", "r", encoding="utf-8-sig") as f:
#         story = Story(f)

#     assert story.continue_() == "A\nX\n"


# def test_implicit_inline_c(compile_story):
#     with open(testdir / "implicit_inline_c.ink.json", "r", encoding="utf-8-sig") as f:
#         story = Story(f)

#     assert story.continue_() == "A\nC\n"


# def test_left_right_matching(compile_story):
#     with open(testdir / "left_right_matching.ink.json", "r", encoding="utf-8-sig") as f:
#         story = Story(f)

#     assert story.continue_() == "A line.\nAnother line.\n"


def test_simple(compile_story):
    story = compile_story("simple")

    assert story.continue_() == "Some content with glue.\n"
