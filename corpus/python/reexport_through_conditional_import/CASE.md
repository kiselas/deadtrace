# A function re-exported by a conditional import

`_util` imports `inet_ntop` from `_inet` on Windows and from the standard library elsewhere, and
`_tool` imports the name from `_util`. The project function is the one that runs on the first
platform, so it is used. `unused` is referenced nowhere.
