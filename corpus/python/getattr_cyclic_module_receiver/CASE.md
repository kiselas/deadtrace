# Cyclic receiver with another module assignment

One receiver is assigned through an alias cycle and from sys.modules. The cycle must not
prevent recognizing the other assignment: a computed getattr call may run a public definition
of a possible module. This is a positive control for conservative module-flow handling,
separate from the ordinary-value case so its broad guard does not hide the unused-method control.
