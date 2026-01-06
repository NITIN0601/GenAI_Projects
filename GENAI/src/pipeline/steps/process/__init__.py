"""
Process step package.

Modular implementation of the Process pipeline step for data processing
and normalization.

This package contains:
- step.py: Main ProcessStep class
- constants.py: Shared constants
- table_finder.py: Table detection utilities
- cell_processor.py: Cell value processing
- key_value_handler.py: Key-value table handling
- header_builders.py: Header building functions
- header_flattener.py: Header flattening logic
"""

from src.pipeline.steps.process.step import ProcessStep

__all__ = ['ProcessStep']
