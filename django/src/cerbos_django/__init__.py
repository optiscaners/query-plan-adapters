import importlib.metadata

from cerbos_django.query import get_queryset, GenericAttribute, OperatorFnMap

__version__ = importlib.metadata.version(__package__ or __name__)

__all__ = ["get_queryset", "GenericAttribute", "OperatorFnMap"]
