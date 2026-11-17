"""Public lifecycle implemented by every registered method."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

@dataclass
class Context:
    storage: object
    scenario: dict
    workspace: Path
    run_id: str
    inputs: dict
    emit: Callable
    cancelled: Callable

    def checkpoint(self):
        if self.cancelled(): raise InterruptedError('Run cancelled')

class Method(ABC):
    def __init__(self,spec): self.spec=spec
    def describe(self): return self.spec
    @abstractmethod
    def validate(self,request,context): """Reject invalid physical assumptions before execution."""
    @abstractmethod
    def prepare(self,request,context): """Build native inputs in the isolated workspace."""
    @abstractmethod
    def execute(self,prepared,context): """Compute and report diagnostics; poll context.checkpoint()."""
    @abstractmethod
    def export(self,result,context): """Return a self-contained protocol payload directory."""
