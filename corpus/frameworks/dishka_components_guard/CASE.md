# Dishka components guard

Components change the namespace used for binding selection. Until component propagation and
`FromComponent` are modeled together, the app world is partial and the affected provider remains
conservatively protected.
