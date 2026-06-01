"""lib.registry — Physical component specifications and COMPONENT_REGISTRY.

This package re-exports all public names so that existing imports like
``from lib.registry import COMPONENTS, ComponentSpec`` continue to work.
"""
from .component_spec import (
    ComponentSpec,
    ConnectorPort,
    ENCLOSURE_RELATIONS,
    MountingHole,
    TAG_VOCAB_AXIS1,
    TAG_VOCAB_AXIS2_PREFIXES,
)
from .registry_data import COMPONENT_REGISTRY
from .component_tags import _split_tags, find_equivalent

__all__ = [
    # Types
    "ComponentSpec",
    "ConnectorPort",
    "MountingHole",
    # Constants
    "COMPONENT_REGISTRY",
    "ENCLOSURE_RELATIONS",
    "TAG_VOCAB_AXIS1",
    "TAG_VOCAB_AXIS2_PREFIXES",
    # Functions
    "find_equivalent",
    "_split_tags",
]
