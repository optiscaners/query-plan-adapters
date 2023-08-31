import importlib.metadata

from cerbos_django.query import get_query, GenericAttribute, OperatorFnMap

__version__ = importlib.metadata.version(__package__ or __name__)

__all__ = ["get_query", "GenericAttribute", "OperatorFnMap"]
