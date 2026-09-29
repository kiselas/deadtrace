# Classes named in quoted annotations

`collect` and `wrap` annotate their parameters and results with strings: `"Options"`,
`"Behaviour"`, `list["Wrapped"]`, and `"dict[str, Named] | None"`. A string annotation names its
class as the unquoted one does, and a checker needs the class: reporting `Options`, `Behaviour`,
`Wrapped`, or `Named` is unsafe. `Unused` appears only in the strings of a `Literal`, which are
values and not types, and stays a candidate.
