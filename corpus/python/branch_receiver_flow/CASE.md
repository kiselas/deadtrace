# Receiver flow safety

The script calls main(True) and main(False). The first constructs First and calls
First.run; the second constructs Second and calls Second.run. At the merge, item can have
either type. A traversal that keeps only the assignment visited last loses First.run.

Both methods must remain outside findings, whether resolved precisely or protected by a
local boundary. _unused_control has no references and must remain a candidate: suppressing
the entire world is not an acceptable fix. Expectations follow from the statements above;
the target is never executed by the scanner or this test.
