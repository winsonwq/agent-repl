from .context import RuntimeContext

ctx = RuntimeContext.load()

__all__ = ["RuntimeContext", "ctx"]
