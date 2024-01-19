# inkpy

This is a Python port of inkle's [ink](https://github.com/inkle/ink), a scripting language for writing interactive
narrative.

inkpy aims to be fully feature [compatiable](#compatibility) with the original version but also have a Pythonic API for
integrating with new and existing game and web frameworks.


## Getting Started

```python

import inkpy


# use a path
story = inkpy.Story("story.json")


# ... or a file-like object
with open("story.json", "f") as f:
    story = inkpy.Story(f)


# ... or you can also pass a string

content = """
- I looked at Monsieur Fogg 
*   ... and I could contain myself no longer.
    'What is the purpose of our journey, Monsieur?'
    'A wager,' he replied.
    * *     'A wager!'[] I returned.
            He nodded. 
            * * *   'But surely that is foolishness!'
            * * *  'A most serious matter then!'
            - - -   He nodded again.
            * * *   'But can we win?'
                    'That is what we will endeavour to find out,' he answered.
            * * *   'A modest wager, I trust?'
                    'Twenty thousand pounds,' he replied, quite flatly.
            * * *   I asked nothing further of him then[.], and after a final, polite cough, he offered nothing more to me. <>
    * *     'Ah[.'],' I replied, uncertain what I thought.
    - -     After that, <>
*   ... but I said nothing[] and <> 
- we passed the day in silence.
- -> END
"""

story = inkpy.Story.from_string(content)

```


## Differences with the C# API

There are a number of API differences between ink C# and inkpy:



### Variable observers

A method or decorator can be used to register a function:

```python

def set_health_in_ui(name, value):
    pass

story.observe_variable("health", set_health_in_ui)


# ... or with a decorator

@story.observe_variable("health")
def set_health_in_ui(name, value):
    pass

```


### Out from ``EvaluationFunction``

The result and text output are returned as a tuple, instead of the text output being passed as an
argument:

```python

result, output = story.evaluation_function("my_ink_function", ["arg1", "arg2"])

```

### Binding external functions

A method or decorator can be used to bind a function:


```python

def play_sound(name):
    pass

story.bind_external_function("playSound", play_sound)


# ... or with a decorator

@story.bind_external_function("playSound")
def play_sound(name):
    pass

```

``lookahreadSafe`` becomes the ``lookahead_safe`` keyword-argument to the method.


## Compiler

You can use the command-line compiler:

```shell

$ python -m inkpy.compiler -h

```

Or compile from within the API:

```python

# you can compile an `<inkjs.Story>` object
story.compile()

# or pass a `<inkjs.Story>` to the `compile` function
inkjs.compile(story)

# ... or you can pass a string containing raw `ink`
inkjs.compile(content)

```


## Compatibility

| _inklecate_ version | _inkpy_ version | _json_ version |
| :-----------------: | :-------------: | :------------: |
|    1.0.0 - 1.1.1    |      0.1.0      |     20 - 21    |
