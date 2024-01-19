
.. code-block:: python

    story.global_tags

    # 'author' and 'title' tags are exposed as attributes
    story.author
    story.title  


.. code-block:: python

    story.reload()  # if story was loaded from a filename

    story.reload(name)

    story.reload(f)


.. warning::

    This does not modify your state or variables so sometimes changing or deleting knots and stitches can leave your
    story in an unstable state.


.. code-block:: python

    while story.can_continue:
        logging.debug(story.continue_())

    # ... or with shortcut

    story.continue_maximally()


.. code-block:: python

    if story.current_choices:
        for choice in story.current_choices:
            logging.debug(f"Choice {choice.index}. {choice.text}" )


    # ... and when player provides input

    story.choose_choice(choice)  # provide the `<inkjs.Choice>` object
    story.choose_choice(index)  # or integer index


.. code-block:: python

    story.state.to_json()
    story.state.load_json(saved_json)

    # ... and you can save/load to dict and serialize/deserialize whatever format

    story.state.to_dict()
    story.state.load_dict(saved_dict)


.. code-block:: python

    story.variables_state["player_health"] == 100

    health = story.variables_state["player_health"]


.. code-block:: python

    @story.observe_variable("health")
    def set_health_in_ui(name, value):
        pass


.. code-block:: python

    result, output = story.evaluation_function("myFunctionName")

    result, output = story.evaluation_function("myFunctionName", lookahead_safe=False)


.. code-block:: python

    @story.bind_external_function("playSound")
    def play_sound(name):
        pass
