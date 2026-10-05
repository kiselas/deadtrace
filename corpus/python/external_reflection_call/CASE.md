# An annotated external instance with mutable names

The parameter's string annotation names Path through a TYPE_CHECKING import. A project subclass
is a valid receiver. The initial dictionary key selects `check`, and the unknown key may select
`arbitrary`. Both methods may run. The dictionary is deliberately mutated: its initializer must
not be treated as an exhaustive list of names. The receiver alias keeps its value provenance.

The private control function has no references and remains a candidate. Expectations come from
Python's instance lookup and the project's declared input type contract, not scanner output.
The annotation is not enforced by Python. The scanner parses this target without executing it.
