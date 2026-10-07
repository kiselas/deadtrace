# Test file named only by a CI workflow

`.github/workflows/tests.yml` runs `python -m pytest checks.py`. `checks.py` matches no `python_files`
pattern, but the file named as an argument is collected, so `test_price` and `price` are not
candidates. `unused` in the tool script is referenced nowhere.
