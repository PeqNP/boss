import importlib.util
import os
import sys

LOADED = []

def get_app_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app")

def get_app_module(module_name):
    # Already loaded
    module = sys.modules.get(module_name, None)
    if module:
        return module

    module_path = os.path.join(get_app_dir(), module_name, "__init__.py")
    if not os.path.isfile(module_path):
        raise Exception(f"App ({module_name}) module not found at path ({module_path})")
    spec  = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
