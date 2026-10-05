# A requested Dishka binding does not protect its class

A service that an endpoint requests through Dishka is reached, and so is every method the
application calls on it. A method that nothing calls is dead code like any other. Only what hangs
below a binding that nothing requests is reported with that binding instead.
