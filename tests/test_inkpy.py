import os

from inkpy.runtime.story import Story


def test_inkpy():
    name = os.path.dirname(__file__) + "/data/tests.ink.json"
    with open(name, "r", encoding="utf-8-sig") as f:
        story = Story(f)
        story.continue_()
