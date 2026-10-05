# ADR-0028: Conventions found in more installed packages (model revision 21)

**Status:** Accepted, 2026-09-29.

## Context

The eleventh field pass scanned seventy more installed packages, from the environments of two field
projects and of a test project: `cryptography`, `ldap3`, `paramiko`, `lxml`, `openai`,
`sqlalchemy`, `greenlet`, `trio`, `py`, `win32com`, `autobahn`, `execnet`, and others. Four of them (`Crypto`, `ecdsa`, `trio`,
`hyperlink`) ended `incomplete` and reported nothing. The other packages had 299 findings, which
three reviewers checked against the sources, member by member. About a third were false. The
mechanisms, each reproduced in a small project:

- **Arguments that Hypothesis fills.** `@given(st.integers())` calls the test with a generated
  value. The tests world read `value` as an unresolved fixture (`DT3201`), which left the world
  partial and, through the widest guard of an unresolved fixture, kept every definition of the
  project: `ecdsa` and `hyperlink` reported nothing.
- **A plugin that `addopts` loads.** `addopts = -p tests.plugin` makes pytest import the module
  before collection, and its fixtures serve every test. The tests of such a project requested
  unresolved fixtures.
- **A base defined in both branches of a condition.** `Generic` is defined under `TYPE_CHECKING`,
  under `PYDANTIC_V2`, and in the `else`, and `class Model(Generic)` derives from whichever ran.
  The alternatives were already handled for calls and references, but not for bases.
- **A name imported in both branches of a condition.** `if sys.platform == "win32": from ._inet
  import inet_ntop`, `else: from socket import inet_ntop`. The re-export chain followed only the
  last import, which is the one from another package.
- **An alias of a class outside the project.** `TestCase = unittest.TestCase` in a helper module and
  `from .util import TestCase` in the tests: the classes were not test cases, and their methods
  were reported.
- **`unittest.main()` in a script.** It collects the test cases of the module it is in.
- **A script that another module runs by its file name.** `subprocess.run([sys.executable,
  "fail_script.py"])`.
- **A name chosen by a computed prefix.** `getattr(self.__class__, "save_" + type(obj).__name__)`
  had a receiver the analyzer did not localize, so the guard covered the whole project.
- **A lazy export table.** `apipkg.initpkg(..., exportdefs={"cmdexec": "._process.cmdexec:cmdexec"})`
  names a definition by a relative string, and the definition may be made in two branches.
- **Names that a host looks up.** `def __ExtensionFactory__()`: Python reserves names of this form,
  and the program that loads the module, an ISAPI host, reads them by name.

## Decision

1. **`@given`.** The keywords of `hypothesis.given` name arguments it fills, and its positional
   strategies fill the rightmost parameters, after `self` or `cls`. They are no fixture requests.
2. **`-p` in `addopts`.** The modules that `addopts` names with `-p name` or `-pname`, from
   `pytest.ini`, `pyproject.toml`, `tox.ini`, or `setup.cfg`, are plugins of the tests world. `-p
   no:name` disables a plugin and names no module.
3. **Bases.** A class inherits from every definition of the name its base statement resolves to.
4. **Re-exports.** A name that a module imports in more than one place is followed through each
   import when a project name is resolved through the module.
5. **Aliases.** `NAME = dotted.name` at the top level of a module, assigned once, gives `NAME` the
   external name it stands for, wherever `NAME` is imported. This covers external bases and the
   `unittest.TestCase` test of pytest collection.
6. **`unittest.main()` and `unittest.TestProgram`.** They reach the `TestCase` classes of the
   module that calls them, with their methods.
7. **File names.** A string that is one relative file name (`[\w./-]+\.py`) and ends the path of at
   most three project modules reaches those modules.
8. **Computed attribute names.** `type(x)` and `x.__class__` have the type of `x`. A computed name
   whose constant start or end is known, directly or through one assignment in the function,
   reaches only the methods of the receiver that begin and end that way.
9. **Relative strings.** `".mod:attr"` and `".mod"` in a string are read relative to the package of
   the module, as an import would be. A string that names a definition also reaches its other
   definitions.
10. **Reserved names.** A function or class in a module named `__like_this__`, other than the
    module hooks of ADR-0025, is an entry point when the module runs.

`MODEL_REVISION` becomes `python-fastapi-dishka/21`.

## Consequences

- The packages had 299 findings before and about 200 after. Names that pytest collects, that a
  table names, and that a host looks up are no longer reported, and `ecdsa` and `hyperlink` are
  complete. The reviewers found the remainder to be true or of the kinds below.
- The field projects and the installed packages of the earlier passes report the same findings as
  before, apart from the implementation of an abstract method that is not reported any more
  (ADR-0027) and the results of the rules above.
- Known and not changed: a package whose own test runner lists module names in strings and loads
  them with `__import__` (`win32com`), COM classes whose methods are named in `_public_methods_`,
  callbacks from compiled extensions (Rust, Cython) and from plugin managers (pluggy), duck-typed
  protocols of a dependency (`to_line` of an object handed to a scanner), names bound to a class
  before a later statement redefines them, and the API of a distribution that a top-level module
  outside the scanned files re-exports. `Crypto` and `trio` stay `incomplete`: their test cases take
  arguments that `unittest` does not fill, and their plugin is registered outside the scanned files.
- Corpus cases fail on revision 20: `python/conditional_base_definition`,
  `python/reserved_module_names`, `python/getattr_prefix_dispatch`,
  `python/reexport_through_conditional_import`, `python/script_run_by_file_name`,
  `python/lazy_export_relative_strings`, `frameworks/pytest_unittest_base_alias`,
  `frameworks/unittest_main_script`, `frameworks/pytest_hypothesis_given`, and
  `frameworks/pytest_plugin_from_addopts`. Accepted.
