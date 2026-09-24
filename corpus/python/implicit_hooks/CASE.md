# Implicit Python hooks

Properties, protocol methods, and project metaclass hooks execute through Python mechanisms that
the alpha does not resolve precisely. When their owning class or module is live, Deadtrace keeps
the hooks and their transitive helpers conservative and reports the limitation instead of hiding
only the hook declaration.
