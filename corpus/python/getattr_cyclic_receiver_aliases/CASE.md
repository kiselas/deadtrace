# Cyclic assignments in an optional getattr receiver

A static walk of assignments must terminate when a local name is rebound through itself or a
cycle of aliases. This does not prove that the value is a module. A known-name optional hook on
an ordinary unknown value still dispatches by name; unrelated methods stay candidates.
The worker's `target` points back to itself, so the rebound receiver can call the hook at runtime.

The separate module-flow control is in `getattr_cyclic_module_receiver`. No target program is
executed to check these expectations.
