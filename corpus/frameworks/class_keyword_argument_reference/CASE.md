# A class passed as a keyword of a class statement

`class UserAdmin(ModelView, model=User)` passes `User` to the base class's `__init_subclass__`, which
runs when the statement executes. `User` is used; `Unused` is referenced nowhere.
