# A script that another module runs by its file name

`_tool.py` starts `_worker.py` in a subprocess by the file's name. The worker's module code runs, and
with it the function and the class it uses. `unused` is referenced nowhere.
