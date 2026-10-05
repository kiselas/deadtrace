# Public factory return API

A library exports `make`. Its declared return type is a project class in a private module.
An external consumer may call `make().run()`, so `Worker.run` cannot safely be removed.
`Worker._unused` is private and has no consumer in this example; it remains a removal candidate.
These expectations follow the library's public return contract, independently of scanner output.
