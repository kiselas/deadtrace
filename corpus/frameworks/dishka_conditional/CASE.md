# Dishka conditional activation

Conditional providers can observe context and registry composition while selecting a binding.
Until that selection is modeled precisely, the application world is partial and negative binding
findings are blocked.

`Service` itself is live: the endpoint's annotation `FromDishka[Service]` is evaluated when the
`def` statement runs, so the class is used whether or not Dishka resolves the demand. The guard
applies to the binding that would provide it.
