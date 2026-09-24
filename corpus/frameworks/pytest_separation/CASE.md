# Production and pytest worlds

Test fixtures form a separate world. A production helper used only through a fixture is reported as
test-only, while a genuinely unreachable production function remains a normal review candidate.
