class TypeMeta(type):
    @property
    def lookups(cls):
        return cls._lookups()


class BaseType(metaclass=TypeMeta):
    @staticmethod
    def _lookups():
        return {}


class NumberType(BaseType):
    @staticmethod
    def _lookups():
        return {"gt": "greater"}

    def _unused(self):
        return None
