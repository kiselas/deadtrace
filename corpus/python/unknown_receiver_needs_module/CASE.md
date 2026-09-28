# Methods on values of unknown type need their module to run

`_tool.py` calls `resource.close()` on a parameter without a type, so any method named `close`
may run. A method runs on an instance, and an instance exists only after its class statement
ran, which happens when its module runs in the same program; a deserializer that
builds instances from data runs the module itself, which `deserialized_receiver`
covers. `_handles.py`, which `_tool.py` imports, defines
`Handle.close`; `_legacy.py`, which nothing imports, defines `Legacy.close`.

The unsafe outcome is reporting `Handle.close`, whose module runs. `Legacy` cannot have an
instance in this program, so it is reported instead of being kept by every unknown `close` call.
