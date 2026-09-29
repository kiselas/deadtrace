# A callback defined in each branch of a condition

`Walker.descendants` defines `fn` three times, once in each branch of an `if`/`elif`/`else`, and
passes whichever ran to `Walker.iterate`, which calls it. Any of the three may run, so none is
unreached. The unsafe outcome is reporting the branches that a single name lookup does not pick.
`Walker.unused` is called by nothing and stays a candidate.
