# A getattr value with a known name

`main` probes each tracker with `prime = getattr(tracker, "prime", None)` and calls the value. That
reads what `tracker.prime` reads: a method named `prime` of any project class may run, so `Rpc.prime`
is protected. `Rpc.other` is named nowhere.
