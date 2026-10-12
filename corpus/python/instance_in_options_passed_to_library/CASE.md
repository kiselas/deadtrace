# A project instance in options passed to a library

`yt_dlp.YoutubeDL(options)` receives `_CollectingLogger()` inside a dict, bound to a local first or written
in the call, and calls its `debug` and `warning` by protocol; `_Direct.info` is reached the same way.
`_Kept()` sits in a dict that is never passed anywhere: `_Kept.run` stays a candidate.
