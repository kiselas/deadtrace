# A receiver annotated with a union of project classes

`Builder.__init__(self, proxy: Plain | Slug)` stores its argument in `self.proxy`, and
`Builder.build` calls `self.proxy.status()`. The program passes a `Slug`, so `Slug.status` runs;
the annotation names two classes, and neither alone is the type of the field.

The unsafe outcome is taking the first class of the union for the type and reporting
`Slug.status`. A function that nothing uses is still reported.
