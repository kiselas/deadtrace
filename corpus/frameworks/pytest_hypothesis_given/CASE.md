# Hypothesis fills the arguments of a test

`@given(strategy)` calls the test with generated values, so the arguments it fills are not
fixture requests: positional strategies fill the rightmost parameters (after `self`) and keyword
strategies fill the parameters they name. Reading them as unresolved fixtures made the tests world
partial and, through its widest guard, kept every definition of the project.
