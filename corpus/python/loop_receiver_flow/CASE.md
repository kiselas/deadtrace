# Receiver flow safety

The script calls main([1, 2]). The first iteration calls First.run and assigns
Second to item; the second iteration calls Second.run. A single traversal of the loop
body resolves the call only before the later assignment, losing the back-edge value.

Both methods must remain outside findings, whether resolved precisely or protected by a
local boundary. _unused_control has no references and must remain a candidate: suppressing
the entire world is not an acceptable fix. Expectations follow from the statements above;
the target is never executed by the scanner or this test.
