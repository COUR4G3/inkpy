import pytest


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "diverts"


def test_basic_tunnel(compile_story):
    story = compile_story("basic_tunnel")

    assert story.continue_() == "Hello world\n"


# def test_same_line_divert_is_inline(testdir):
#     with open(testdir / "complex_tunnels.ink.json", "r", encoding="utf-8-sig") as f:
#         story = Story(f)

#     assert story.continue_() == "We hurried home to Savile Row as fast as we could.\n"


def test_complex_tunnels(compile_story):
    story = compile_story("complex_tunnels")

    assert story.continue_() == "one (1)\none and a half (1.5)\ntwo (2)\nthree (3)\n"


# def test_divert_targets(testdir):
#     with open(
#         testdir / "compare_divert_targets.ink.json", "r", encoding="utf-8-sig"
#     ) as f:
#         story = Story(f)

#     assert (
#         story.continue_()
#         == "different knot\nsame knot\nsame knot\ndifferent knot\nsame knot\nsame knot\n"
#     )


# def test_tunnel_onwards_after_tunnel(testdir):
#     with open(
#         testdir / "tunnel_onwards_after_tunnel.ink.json", "r", encoding="utf-8-sig"
#     ) as f:
#         story = Story(f)

#     assert story.continue_() == "Hello...\n...world.\nThe End.\n"


# def test_tunnel_onwards_divert_after_with_arg(testdir):
#     with open(
#         testdir / "tunnel_onwards_divert_after_with_arg.ink.json",
#         "r",
#         encoding="utf-8-sig",
#     ) as f:
#         story = Story(f)

#     assert story.continue_() == "8\n"


# def test_tunnel_onwards_divert_override(testdir):
#     with open(
#         testdir / "tunnel_onwards_divert_override.ink.json", "r", encoding="utf-8-sig"
#     ) as f:
#         story = Story(f)

#     assert story.continue_() == "This is A\nNow in B.\n"
