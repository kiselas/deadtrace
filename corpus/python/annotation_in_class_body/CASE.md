# A nested class named bare in the body of its class

`items: list[Item]` and `def head(self) -> Row` are evaluated in the body of `Request`, where a bare
name is a member of `Request` first: `Item` and `Row` are `Request.Item` and `Request.Row`, and they
are used. `Request.Unused` is referenced nowhere.
