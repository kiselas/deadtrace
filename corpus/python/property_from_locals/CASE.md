# A property built from the locals of a function

`Filter.label` is made the classic way: a function defines `fget` and `fset` and returns
`locals()`, and `property(**label())` builds the property from that dictionary. Both functions
run when the attribute is read or written, though nothing names them. Reporting them is unsafe.
`Filter.unused` is called by nothing and stays a candidate.
