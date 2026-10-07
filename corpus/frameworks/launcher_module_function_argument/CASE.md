# A launcher names a function as `module:function`

`deploy/hello.conf` runs `launcher launch-ui _hello:run`. The launcher is unknown to the model, but
the argument names a project module and function, so `run` is a root. `unused` in the same
module is referenced nowhere.
