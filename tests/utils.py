import os

from inkpy.runtime.story import Story


def load(name):
    def error_on_first_error(message, is_warning=False):
        raise RuntimeError(message)

    name = os.path.dirname(__file__) + f"/data/{name}"
    with open(name, "r", encoding="utf-8-sig") as f:
        story = Story(f)

    story._on_error = error_on_first_error

    return story


def load_and_continue(name):
    story = load(name)
    return story, story.continue_()


def load_and_continue_maximally(name):
    story = load(name)
    return story, "".join(story.continue_maximally())
