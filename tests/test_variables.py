import pytest

from .utils import load, load_and_continue


def test_const():
    _, output = load_and_continue("variables/const.ink.json")
    assert output == "5\n"


def test_multiple_constant_references():
    _, output = load_and_continue("variables/multiple_constant_references.ink.json")
    assert output == "success\n"


def test_set_non_existent_variable():
    story, output = load_and_continue("variables/set_non_existent_variable.ink.json")
    assert output == "Hello world.\n"
    assert not story.state.variables_state.get_variable_with_name("y")


def test_temp_global_conflict():
    output = load_and_continue("variables/temp_global_conflict.ink.json")
    assert output == "0\n"


def test_temp_not_found():
    story = load("variables/temp_not_found.ink.json")

    output = None
    with pytest.raises(RuntimeError):
        output = "".join(text for text in story.continue_maximally())

    assert not output
    assert story.has_warning


def test_temp_usage_in_options():
    story, _ = load_and_continue("variables/temp_usage_in_options.ink.json")
    assert len(story.current_choices) == 1
    assert story.current_choices[0].text == "1"

    story.choose_choice_index(0)
    output = "".join(text for text in story.continue_maximally())

    assert output == "1\nEnd of choice\nthis another\n"
    assert len(story.current_choices) == 0


def test_temporaries_at_global_scope():
    _, output = load_and_continue("variables/temporaries_at_global_scope.ink.json")
    assert output == "54\n"


def test_variable_divert_target():
    _, output = load_and_continue("variables/variable_divert_target.ink.json")
    assert output == "Here.\n"
