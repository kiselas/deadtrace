# An instance handed to a library that calls its methods

`serve` passes `Handler(25)` to an SMTP `Controller`, and a `Handler` bound to a name to a
second one; the library calls `handle_DATA` on the handler for every message it receives.
`show` passes a `Report` to `print`, which calls only its special methods.

The unsafe outcome is reporting `Handler.handle_DATA`, which the library calls although no
project code does. `Report.unused` is still reported, as `print` calls no ordinary method.
