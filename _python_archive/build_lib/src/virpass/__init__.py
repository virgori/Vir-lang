"""
VirPass — Compiler pass framework for QIR.
"""

from src.virpass.base_pass import BasePass, PassResult
from src.virpass.pass_manager import PassManager

__all__ = ["BasePass", "PassResult", "PassManager"]
