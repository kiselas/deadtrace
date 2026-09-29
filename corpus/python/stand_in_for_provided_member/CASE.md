# A stand-in for an object whose member a base provides

`Service` takes `gateways: Gateways` and calls `gateways.mikrotik()`. `Gateways` is a container
whose base supplies `mikrotik` as an attribute, so the class has no method of that name. The test
passes `_GatewaysStub`, a hand-written stand-in, so `_GatewaysStub.mikrotik` runs. Reporting it is
unsafe. `_GatewaysStub.other` matches no call and stays a candidate.
