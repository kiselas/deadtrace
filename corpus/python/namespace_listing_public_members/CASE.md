# Listing the members of a value of unknown type

`rpc_methods` lists the methods of the value it receives with `inspect.getmembers` and keeps the
public ones. The value has no known type, so the public members of project classes, `Service.ping`
among them, are protected. `Service._internal` is private: code that lists any value's members has
no reason to use it, and the class itself never calls it.
