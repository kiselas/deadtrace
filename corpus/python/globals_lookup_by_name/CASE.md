# A top-level function looked up by a computed name

`render` picks a renderer with `globals()["_render_%s_type" % kind]`, and a helper with
`globals().get("_named")`. The computed name has the constant start `_render_` and end `_type`,
so `_render_ARRAY_type` and `_render_JSON_type` may run; the constant name reaches `_named`.
Reporting them is unsafe. `_render_other` does not match the start and end and is called by
nothing, so it stays a candidate.
