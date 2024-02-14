import pytest


@pytest.fixture(scope="module")
def testdir(datadir):
    return datadir / "variables"


def test_const(compile_story):
    story = compile_story("const")

    assert story.continue_() == "5\n"


# def test_multiple_constant_references(compile_story):
#     story = compile_story("multiple_constant_references")

#     assert story.continue_() == "success\n"


def test_set_non_existent_variable(compile_story):
    story = compile_story("set_non_existent_variable")

    assert story.continue_() == "Hello world.\n"
    assert story.state.variables_state["y"] is None


def test_temp_global_conflict(compile_story):
    story = compile_story("temp_not_found")

    assert story.continue_() == "0\n"


def test_temp_not_found(compile_story):
    story = compile_story("temp_not_found")

    assert "".join(story.continue_maximally()) == "0\nhello\n"
    assert story.has_warning is True


# TODO: tests_temp_usage_in_options


def test_temporaries_at_global_scope(compile_story):
    story = compile_story("temporaries_at_global_scope")

    assert story.continue_() == "54\n"


def test_variable_declaration_in_conditional(compile_story):
    story = compile_story("variable_declaration_in_conditional")

    assert story.continue_() == "5\n"


def test_variable_divert_target(compile_story):
    story = compile_story("variable_divert_target")

    assert story.continue_() == "Here.\n"


def test_variable_get_set_api(compile_story):
    story = compile_story("variable_get_set_api")

    assert "".join(story.continue_maximally()) == "5\n"
    assert story.state.variables_state["x"] == 5

    story.state.variables_state["x"] = 10
    story.choose_choice_index(0)
    assert "".join(story.continue_maximally()) == "10\n"
    assert story.state.variables_state["x"] == 10

    story.state.variables_state["x"] = 8.5
    story.choose_choice_index(0)
    assert "".join(story.continue_maximally()) == "8.5\n"
    assert pytest.approx(story.state.variables_state["x"], 8.5)

    story.state.variables_state["x"] = "a string"
    story.choose_choice_index(0)
    assert "".join(story.continue_maximally()) == "a string\n"
    assert story.state.variables_state["x"] == "a string"

    assert story.state.variables_state["z"] is None

    with pytest.raises(ValueError):
        story.state.variables_state["x"] = {}


def test_variable_pointer_ref_from_knot(compile_story):
    story = compile_story("variable_pointer_ref_from_knot")

    assert story.continue_() == "6\n"


def test_variable_swap_recurse(compile_story):
    story = compile_story("variable_swap_recurse")

    assert "".join(story.continue_maximally()) == "1 2\n"


def test_variable_tunnel(compile_story):
    story = compile_story("variable_tunnel")

    assert "".join(story.continue_maximally()) == "STUFF\n"
