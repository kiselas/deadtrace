# Methods of objects that a deserializer builds

`_api.py` runs `execute(pickle.loads(payload))`, and `execute(job)` calls `job.run()` on a value
of unknown type. `pickle` imports the module of the pickled object's class, `_jobs`, while it
loads the data, although nothing in the program imports `_jobs`; another program pickled the
`Job`.

The unsafe outcome is reporting `Job.run` because the module defining it is not reached, which
is what keeps methods of unknown receivers from being protected otherwise. A function that
nothing uses is still reported.
