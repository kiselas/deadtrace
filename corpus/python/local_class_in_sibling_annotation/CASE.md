# A local class named in a sibling class's field annotation

`test_hydrate` defines the dataclasses `Pet` and `Person`, whose field is `pets: list[Pet]`, and hands
`Person` to `make_schema`, which reads the field types. The class body of `Person` evaluates the
annotation and finds `Pet` in the enclosing function, so `Pet` is used. `Unused` is named nowhere.
