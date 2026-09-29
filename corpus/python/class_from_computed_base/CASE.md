# A class statement whose base is a value

`_lib.py` builds `Draft7 = create()`, a class made by a project function whose
`__init_subclass__` warns. `_tool.py` derives from it in `check_factory`, from a parameter in
`check_parameter`, where the base is whatever the caller passes, and from the result of a call of
`create` in `check_call`. None of the derived classes is used again: the statements run for the
effect their base's hook has, as a test of a deprecation does. Reporting `FromFactory`,
`FromParameter`, or `FromCall` is unsafe. `Plain` has no base and no effect and stays a candidate.
