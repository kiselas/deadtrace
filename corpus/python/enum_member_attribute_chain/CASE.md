# Attribute chains through enumeration members

`Status.ACTIVE.value` evaluates `Status` although `Status.ACTIVE` is not a definition of the
project. A class-body constant such as `DEFAULT = Status.ACTIVE.value` evaluates it when the
class statement runs.

The unsafe outcome is reporting `Status` or `Level` as unreached because the chain did not
resolve past its second part. An enumeration that nothing uses is still reported.
