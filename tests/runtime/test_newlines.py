import pytest

from inkpy.runtime.path import Path


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "newlines"


# def test_newline_at_start_of_multiline_conditional(compile_story):
#     story = compile_story("newline_at_start_of_multiline_conditional")

#     assert "".join(story.continue_maximally()) == "X\nx\n"


def test_newline_consistency(compile_story):
    story = compile_story("newline_consistency_1")

    assert "".join(story.continue_maximally()) == "hello world\n"

    # TODO: other consistency tests


# def test_newlines_trimming_with_func_external_fallback(compile_story):
#     story = compile_story("newlines_trimming_with_func_external_fallback")
#     story.allow_external_function_fallbacks = True

#     assert "".join(story.continue_maximally()) == "Phrase 1\nPhrase 2\n"


# def test_newlines_with_string_eval(compile_story):
#     story = compile_story("newlines_with_string_eval")

#     assert "".join(story.continue_maximally()) == "A\nB\nA\n3\nB\n"
