# ddt supplies the arguments of a test method

`@data` of ddt calls `test_double` with `value` and `expected`, so they are values and not
fixtures. The test world stays complete: `DoubleTest`, `test_double`, and `double` are not candidates.
`unused` in the tool script is referenced nowhere.
