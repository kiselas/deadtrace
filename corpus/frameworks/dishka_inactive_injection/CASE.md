# Inactive Dishka integration

A `FromDishka` annotation without active `inject`/`DishkaRoute` is not treated as a resolved demand.
The incomplete assembly blocks negative findings for the affected world.

`Service` itself is live: the endpoint's annotation `FromDishka[Service]` is evaluated when the
`def` statement runs, so the class is used whether or not Dishka resolves the demand. The guard
applies to the binding that would provide it.
The guard over the demanded type therefore protects nothing that is not already live, so it adds
no `DT2002` limitation; `DT3101` still marks the world incomplete.
