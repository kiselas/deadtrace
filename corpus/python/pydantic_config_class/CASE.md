# Pydantic configuration class

Pydantic reads a model's nested `Config` class when it builds the model, so the class and the
functions it names run whenever the model is used, although no project code refers to `Config`.

The unsafe outcome is reporting `Item.Config` or the alias generator it names as unreached. A
nested class of a plain class that nothing uses is still reported.
