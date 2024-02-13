import pytest

from inkpy.runtime.path import Path


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "misc"


def test_empty(compile_story):
    story = compile_story("empty")

    assert "".join(story.continue_maximally()) == ""


def test_end_of_content_hello_world(compile_story):
    story = compile_story("end_of_content_hello_world")

    "".join(story.continue_maximally())
    assert len(story.current_errors) == 0

    story = compile_story("end_of_content_with_end")

    "".join(story.continue_maximally())
    assert len(story.current_errors) == 0


def test_end(compile_story):
    story = compile_story("end")

    assert "".join(story.continue_maximally()) == "hello\n"


def test_end2(compile_story):
    story = compile_story("end2")

    assert "".join(story.continue_maximally()) == "hello\n"


# def test_escape_character(compile_story):
#     story = compile_story("escape_character")

#     assert "".join(story.continue_maximally()) == "this is a '|' character\n"


def test_hello_world(compile_story):
    story = compile_story("hello_world")

    assert story.continue_() == "Hello world\n"


# def test_identifiers_can_start_with_number(compile_story):
#     story = compile_story("identifiers_can_start_with_number")

#     assert "".join(story.continue_maximally()) == "512x2 = 1024\n512x2p2 = 1026\n"


# def test_include(compile_story):
#     story = compile_story("include")

#     assert (
#         "".join(story.continue_maximally())
#         == "This is include 1.\nThis is include 2.\nThis is the main file.\n"
#     )


# def test_nested_include(compile_story):
#     story = compile_story("nested_include")

#     assert (
#         "".join(story.continue_maximally())
#         == "The value of a variable in test file 2 is 5.\nThis is the main file\nThe value when accessed from knot_in_2 is 5.\n"
#     )


# def test_quote_character_significance(compile_story):
#     story = compile_story("quote_character_significance")

#     assert "".join(story.continue_maximally()) == 'My name is "Joe"\n'


# def test_whitespace(compile_story):
#     story = compile_story("whitespace")

#     assert "".join(story.continue_maximally()) == "Hello!\nWorld.\n"


def test_paths():
    path1 = Path("hello.1.world")
    path2 = Path("hello.1.world")
    path3 = Path(".hello.1.world")
    path4 = Path(".hello.1.world")

    assert path1 == path2
    assert path3 == path4
    assert path1 != path3


# def test_author_warnings_inside_content_list_bug(compile_story):
#     story = compile_story("author_warnings_inside_content_list_bug")

#     assert len(story.current_errors) == 0
