from dataclasses import dataclass

from schemalib import make_schema


def test_hydrate():
    @dataclass
    class Pet:
        name: str

    @dataclass
    class Person:
        pets: list[Pet]

    @dataclass
    class Unused:
        name: str

    assert make_schema(Person)
