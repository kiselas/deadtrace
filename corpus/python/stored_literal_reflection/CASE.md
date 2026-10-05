# A stored literal attribute can execute a method

`main` constructs `Worker`, retrieves its bound `run` method with `getattr(worker, "run")`,
and calls the resulting callback. Python attribute lookup binds this method to the instance;
`Worker.run` may run and must not be a removal candidate. `Worker.idle` is an independent
unreferenced control. These expectations follow from the source, without scanner output or
executing the target. Moving the call out of the getattr expression must not remove protection.
