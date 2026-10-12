# ADR-0075: Instances in literal containers passed to a consumer

**Status:** Accepted, 2026-10-12; model revision 57.

An instance of a project class passed to an external consumer may have its methods called by
protocol (ADR-0022): `Controller(Handler(port))`. Libraries more often take such objects inside an
options dict: `yt_dlp.YoutubeDL({"logger": _CollectingLogger()})`, written in the call or bound to a
local first. The instance inside the container was not seen, and its `debug`, `info` and `warning`
were reported as unreached (7 reviewed findings, `duck-typed-dependency-protocol`).

For a call to a consumer that may call instance methods, literal dicts, lists, tuples and sets in its
arguments are opened up to three levels deep, as is a local that the same scope assigns such a
literal; each element that constructs a project class makes that class escape to the consumer, as a
direct argument does. Containers that are never passed to a consumer are not opened.

The case `corpus/python/instance_in_options_passed_to_library` fails on revision 56.

MODEL_REVISION becomes `python-fastapi-dishka/57`.
