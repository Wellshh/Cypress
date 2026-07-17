"""Feature-gated placement constraints implemented outside native operators."""

from .pcb_geometry import GeometryAlignment, PCBGeometry, load_pcb_geometry

__all__ = ["GeometryAlignment", "PCBGeometry", "load_pcb_geometry"]
