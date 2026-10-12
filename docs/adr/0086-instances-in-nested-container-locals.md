# ADR-0086: Instances reach a consumer through nested container locals

**Status:** Accepted, 2026-10-12; model revision 69.

ADR-0075 lets a consumer outside the project call the methods of instances held in a literal
container passed to it, directly or through a local that the scope assigns a literal container.
Option dictionaries are often built in steps:

```python
base = {"outtmpl": dest, "logger": _CollectingLogger()}
attempts = [base]
attempts.append({**base, "cookiefile": cookies})
for opts in attempts:
    with yt_dlp.YoutubeDL(opts) as ydl:
        ...
```

The argument `opts` is a loop variable over a container local, and the instance sits in a second
container local that the first holds, so the logger's methods were reported (five reviewed
findings of one cohort project, verdict false).

The rule now also opens a container local named inside an opened container, `**base` included,
and treats a loop variable over a container local as an element of it. The same limits hold: only
literal containers that the scope assigns, three levels at most, and only consumers that call
methods of what they receive.

The case `corpus/python/instances_in_nested_container_locals` fails on revision 68.

MODEL_REVISION becomes `python-fastapi-dishka/69`.
