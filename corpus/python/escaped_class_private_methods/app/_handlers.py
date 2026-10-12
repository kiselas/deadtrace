class Handler:
    def handle(self, payload):
        return self._parse(payload)

    def _parse(self, payload):
        return payload.strip()

    def _stale(self, payload):
        return payload.lower()

    def _repr_html_(self):
        return "<b>handler</b>"

    def __call__(self, payload):
        return self.handle(payload)
