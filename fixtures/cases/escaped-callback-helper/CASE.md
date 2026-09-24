# Escaped callback and transitive helper

The callback crosses an unknown execution boundary. The protection must propagate to
`callback_helper`; protecting only the callback declaration is an unsafe result.
