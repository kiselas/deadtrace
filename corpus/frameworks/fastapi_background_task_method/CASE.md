# A method of an instance built in place, queued as a background task

A route runs `background_tasks.add_task(Cleanup(user).run, True)`: the method of a `Cleanup`
built in the argument is queued, and FastAPI calls it after the response. `run` calls `helper`.

The unsafe outcome is reporting `Cleanup.run` and `Cleanup.helper`, because the method is passed
as a value of an expression that is not a name. A method that nothing uses is still reported.
