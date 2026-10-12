def load(module_name, kind, path="app._validators"):
    mod = __import__(f"{path}.{module_name}", fromlist=[kind])
    return getattr(mod, kind)
