"""Compatibility entrypoint for existing OpenClaw demo images."""

from aidev_agent_adapter.services.openclaw import main, run

__all__ = ["main", "run"]

if __name__ == "__main__":
    main()
