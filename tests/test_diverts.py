from .utils import load, load_and_continue, load_and_continue_maximally


def test_basic_tunnel():
    _, output = load_and_continue("diverts/basic_tunnel.ink.json")
    assert output == "Hello world\n"


def test_compare_divert_targets():
    _, output = load_and_continue_maximally("diverts/compare_divert_targets.ink.json")
    assert (
        output
        == "different knot\nsame knot\nsame knot\ndifferent knot\nsame knot\nsame knot\n"
    )


def test_complex_tunnels():
    _, output = load_and_continue_maximally("diverts/complex_tunnels.ink.json")
    assert output == "one (1)\none and a half (1.5)\ntwo (2)\nthree (3)\n"


def test_divert_in_conditional():
    _, output = load_and_continue_maximally("diverts/divert_in_conditional.ink.json")
    assert output == ""


def test_divert_targets_with_parameters():
    _, output = load_and_continue_maximally(
        "diverts/divert_targets_with_parameters.ink.json"
    )
    assert output == "5\n"


def test_divert_to_weave_points():
    _, output = load_and_continue_maximally("diverts/divert_to_weave_points.ink.json")
    assert output == "gather\ntest\nchoice content\ngather\nsecond time round\n"


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""


def test_done_same_line_divert_is_inline():
    _, output = load_and_continue_maximally(
        "diverts/same_line_divert_is_inline.ink.json"
    )
    assert output == "We hurried home to Savile Row as fast as we could.\n"


def test_tunnel_onwards_after_tunnel():
    _, output = load_and_continue_maximally(
        "diverts/tunnel_onwards_after_tunnel.ink.json"
    )
    assert output == "Hello...\n...world.\nThe End.\n"


def test_tunnel_onwards_divert_after_with_arg():
    _, output = load_and_continue_maximally(
        "diverts/tunnel_onwards_divert_after_with_arg.ink.json"
    )
    assert output == "8\n"


def test_tunnel_onwards_divert_override():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == "This is A\nNow in B.\n"


def test_tunnel_onwards_with_param_default_choice():
    _, output = load_and_continue_maximally(
        "diverts/tunnel_onwards_with_param_default_choice.ink.json"
    )
    assert output == "8\n"


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""


def test_done_stops_thread():
    _, output = load_and_continue_maximally("diverts/done_stops_thread.ink.json")
    assert output == ""
