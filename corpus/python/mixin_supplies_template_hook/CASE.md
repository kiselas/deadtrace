# A mixin supplies the hook a base class calls on self

`BaseQuery.run` calls `self._filter`. `SortQuery(_NoFilterMixin, BaseQuery)` lists the mixin first, so its
MRO finds `_NoFilterMixin._filter`: that method runs. `_UnusedMixin` is a base of no class and its
`_filter` never runs.
