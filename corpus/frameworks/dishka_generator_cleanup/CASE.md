# Dishka generator provider cleanup

A demanded generator provider executes both acquisition and finalization code. The helper after
`yield` must remain reachable; it is not dead merely because it runs when the request scope exits.
