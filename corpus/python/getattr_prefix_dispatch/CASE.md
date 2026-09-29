# A method chosen by a computed prefix

`getattr(self.__class__, "save_" + type(obj).__name__)` reads a method of the class whose name
starts with `save_`. The guard covers those methods, not everything in the project, so `other`,
which nothing calls, is reported.
