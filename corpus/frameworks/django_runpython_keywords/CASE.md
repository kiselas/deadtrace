# RunPython callbacks passed by keyword

`migrations.RunPython(code=forwards, reverse_code=migrations.RunPython.noop)` names its
callbacks by keyword, as Django's signature `RunPython(code, reverse_code=None, ...)` allows.
A second operation passes `forwards` by position and `backwards` as `reverse_code=`.
Django runs `forwards` when the migration is applied and `backwards` when it is reversed,
in `manage.py migrate`, which the world `production:migrations` stands for.

The unsafe outcome is treating the operation as an unresolvable callback, which leaves the
migrations world partial and reports nothing; the callbacks must be retained and the analysis
complete. A function that nothing uses is still reported.
