# An annotation that reads an attribute of a nested class

`fire(data: Meta.Models.EventDataType)` evaluates `Meta.Models.EventDataType` when the `def` runs.
`EventDataType` is an alias assigned in the body of `Meta.Models`, not a definition, so the chain
resolves to no member; it still needs `Meta` and `Meta.Models` to exist, as a class attribute read
does (ADR-0027). `Meta.Unused` is referenced nowhere.
