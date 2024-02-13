import pytest


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "strings"


def test_string_constants(compile_story):
    story = compile_story("string_constants")

    assert story.continue_() == "hi\n"


# def test_string_contains(compile_story):
#     story = compile_story("string_contains")

#     assert "".join(story.continue_maximally()) == "true\nfalse\ntrue\ntrue\n"


# def test_string_type_coercion(compile_story):
#     story = compile_story("string_type_coercion")

#     assert "".join(story.continue_maximally()) == "same\ndifferent\n"


# def test_strings_in_choices(compile_story):
#     story = compile_story("strings_in_choices")

#     for _ in story.continue_maximally():
#         pass

#     assert len(story.current_choices) == 1
#     assert story.current_choices[0].text == 'test "1 test 2 tests3"'

#     story.choose_choice_index(0)
#     assert story.continue_() == "test 1 test4\n"
