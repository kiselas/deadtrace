# A script that puts its own directory on sys.path

`_tools/cli.py` inserts its directory into `sys.path` and does `import console`, which is the sibling
`_tools/console.py` although `_tools` is a package. `colour` is used; `unused` is called nowhere.
