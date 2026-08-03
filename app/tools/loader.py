import importlib
import pkgutil

from app.core.logger import logger
from app.tools.registry import ToolRegistry

registry = ToolRegistry()

_loaded = False


def load_plugins() -> ToolRegistry:
    """
    Discover and register tool packages under app.tools.

    Idempotent: subsequent calls are no-ops.
    """
    global _loaded

    if _loaded:
        return registry

    import app.tools

    package = app.tools

    for _, module_name, ispkg in pkgutil.iter_modules(package.__path__):
        if not ispkg:
            continue

        module_path = f"app.tools.{module_name}"

        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.warning("Failed to import plugin '%s': %s", module_name, exc)
            continue

        tool = getattr(module, "tool", None)
        if tool is None:
            logger.warning(
                "Skipping package '%s': no 'tool' export found",
                module_name,
            )
            continue

        try:
            registry.register(tool)
            logger.info("Registered tool: %s", tool.manifest.name)
        except Exception as exc:
            logger.warning(
                "Failed to register plugin '%s': %s",
                module_name,
                exc,
            )

    _loaded = True
    return registry
