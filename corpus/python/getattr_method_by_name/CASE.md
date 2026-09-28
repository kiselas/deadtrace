# A method looked up by a computed name

`send_email` receives the name of a message generator from a task queue and runs
`getattr(core, name, None)` on a `MailCore`, then passes the method on to be called. Any method
of `MailCore` may be the one, including those of its mixin `Messages`. `Visitor.visit` runs
`getattr(self, "visit_" + kind)()` in a base class; the method is one of the subclass `Printer`,
whose instance is the one visiting.

The unsafe outcome is reporting `Messages.welcome` or `Printer.visit_name` because no call
names them, or considering only methods defined in the receiver's own class. A function that
nothing uses is still reported.
