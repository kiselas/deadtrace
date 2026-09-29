# A generic class named only by a subscripted annotation

`use` annotates its parameter with `Box[int]` and its return with `type[Reader[int]]`. With
postponed evaluation nothing runs the annotation, but the classes are the types of the signature
and a checker needs them: reporting `Box` or `Reader` as unreached is unsafe. `Unused` is named by
nothing and stays a candidate.
