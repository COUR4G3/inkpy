import pytest


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "tags"


def test_tags_constants(compile_story):
    story = compile_story("tags")

    global_tags = ["author: Joe", "title: My Great Story"]
    knot_tags = ["knot tag"]
    knot_tags_when_continued_twice = ["end of knot tag"]
    stitch_tags = ["stitch tag"]

    assert story.global_tags == global_tags
    assert story.continue_() == "This is the content\n"
    assert story.global_tags == global_tags

    assert story.tags_for_content_at_path("knot") == knot_tags
    assert story.tags_for_content_at_path("knot.stitch") == stitch_tags

    story.choose_path_string("knot")
    assert story.continue_() == "Knot content\n"
    assert story.current_tags == knot_tags
    assert story.continue_() == ""
    assert story.current_tags == knot_tags_when_continued_twice


# def test_tags_in_seq(compile_story):
#     story = compile_story("tags_in_seq")

#     assert story.continue_() == "A red sequence\n"
#     assert story.current_tags == ["red"]

#     assert story.continue_() == "A white sequence\n"
#     assert story.current_tags == ["white"]


# def test_tags_dynamic_content(compile_story):
#     story = compile_story("tags_dynamic_content")

#     assert story.continue_() == "tag\n"
#     assert story.current_tags == ["pic8red.jpg"]
