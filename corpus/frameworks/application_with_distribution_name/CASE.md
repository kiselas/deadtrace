# An application that declares a distribution is not a library

`pyproject.toml` names the distribution `shop-app` and declares a console script. Its package
`shop_app` is an application, not an API for other projects: the unused function in it must still
be reported. The script world roots the command, and no library world protects the package's other
public names.
