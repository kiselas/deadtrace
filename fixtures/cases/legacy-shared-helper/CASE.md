# Legacy component with a shared helper

`LegacyService` is expected to become a candidate, while `normalize` must stay alive because
the supported endpoint also uses it. Grouping must not absorb shared dependencies.
