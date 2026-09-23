"""OpenCode grey-box plugin hook capture; never install for black-box cases."""

from agent_models.opencode.hooks.capture import OpenCodeHookCapture

__all__ = ["OpenCodeHookCapture"]
