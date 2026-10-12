# An instance passed through nested container locals

`download` builds `base = {"logger": _CollectingLogger()}`, keeps it in `attempts = [base]` (and in
`{**base, ...}`), and passes each element to `yt_dlp.YoutubeDL(opts)` in a loop. The library calls the
logger's `debug`, `warning`, and `error` by protocol, so they are protected by the consumer.
`_Unused` is never instantiated.
