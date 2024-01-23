import logging

from inkpy.runtime.story import Story


logging.basicConfig(level=logging.DEBUG)


f = open("tests/data/the_intercept.ink.json", "r", encoding="utf-8-sig")

story = Story(f)
