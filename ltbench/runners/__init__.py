"""Runner adapters that wrap a translation system to produce LTB-format submissions."""

from ltbench.runners.base import Runner
from ltbench.runners.identity import IdentityRunner

__all__ = ["Runner", "IdentityRunner"]
