import importlib
import pkgutil

from app.tools.registry import ToolRegistry

registry = ToolRegistry()


def load_plugins():
    import app.tools

    package = app.tools

    for _, module_name, ispkg in pkgutil.iter_modules(package.__path__):

        if not ispkg:
            continue

        module = importlib.import_module(
            f"app.tools.{module_name}"
        )

        registry.register(module.tool)
