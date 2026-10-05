# A public object's public fields expose another object's API

The package exports Manager. A library user can construct it and call
`Manager().trace.root.setwriter(writer)`: both trace and root are public attributes, and their
project types are evident from annotations/constructor assignments. `Trace.setwriter` may execute
from an external caller and must not be a removal candidate. Its unreferenced private `_unused`
method is not part of this public chain and remains a candidate. These expectations follow from
the source and the library public-API contract, independently of scanner output. No target code
is executed by the scanner.
