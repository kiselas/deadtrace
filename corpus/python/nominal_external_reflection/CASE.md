# A standard nominal family, with an opaque base control

A Path parameter may be a ProjectPath and its runtime attribute name may be `check`.
The unscanned Bridge may itself derive from Path, so OpaquePath.check must also stay protected.
The plain Unrelated class derives from neither Path nor an opaque base; its idle method has
no references and remains a candidate under the declared nominal input contract. No name-table
immutability is assumed. The scanner never imports external or executes this target.
