class Llm:
    def saveState(self, model_id):
        return model_id

    def load_cache(self):
        return {}

    def _unused(self):
        return None


def helper():
    return "never called"
