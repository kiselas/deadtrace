# A plugin fixture requested by name from another fixture

`pkg/plugin.py` is a pytest plugin of a library and holds no tests. The public fixture `faker`
calls `request.getfixturevalue("_session_value")`, so the private fixture runs when a user's test
asks for `faker`, though no signature names it. Reporting `_session_value` is unsafe.
`_unused_helper` is called by nothing and stays a candidate.
