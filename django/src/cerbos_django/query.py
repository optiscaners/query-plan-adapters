from functools import reduce
from operator import and_, or_
from types import MappingProxyType
from typing import Any, Callable, cast, Dict, TypeVar, Iterable, Union, Optional

from cerbos.engine.v1 import engine_pb2
from cerbos.response.v1 import response_pb2
from cerbos.sdk.model import PlanResourcesFilterKind, PlanResourcesResponse
from dataclasses_json import DataClassJsonMixin
from django.db.models import Model as _Model, Q, Field, ManyToOneRel, ManyToManyRel
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ReverseManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
)
from django.db.models.query_utils import DeferredAttribute
from google.protobuf.json_format import MessageToDict

Model = TypeVar("Model", bound=_Model)
OperatorFnMap = Dict[str, Callable[[str, Any], Q]]
ExplicitAttribute = Union[
    str,
    Field,
    DeferredAttribute,
    ForwardManyToOneDescriptor,
    ReverseManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
]
ChainedAttribute = Iterable[ExplicitAttribute]
GenericAttribute = Union[ExplicitAttribute, ChainedAttribute]

# We want to make the base dict "immutable", and enforce explicit (optional) overrides on
# each call to `get_query` (rather than allowing keys in this dict to be overridden, which
# could wreak havoc if different calls from the same memory space weren't aware of each other's
# overrides)
__operator_fns: OperatorFnMap = {
    "eq": lambda c, v: Q(**{c: v}),  # c, v denotes column, value respectively
    "ne": lambda c, v: ~Q(**{c: v}),
    "lt": lambda c, v: Q(**{c + "__lt": v}),
    "gt": lambda c, v: Q(**{c + "__gt": v}),
    "le": lambda c, v: Q(**{c + "__lte": v}),
    "ge": lambda c, v: Q(**{c + "__gte": v}),
    "in": lambda c, v: Q(**{c + "__in": [v] if not isinstance(v, list) else v}),
}
OPERATOR_FNS = MappingProxyType(__operator_fns)

# We support both the legacy HTTP and gRPC clients, so therefore we need to accept both input types
_deny_types = frozenset(
    [
        PlanResourcesFilterKind.ALWAYS_DENIED,
        engine_pb2.PlanResourcesFilter.KIND_ALWAYS_DENIED,
    ]
)
_allow_types = frozenset(
    [
        PlanResourcesFilterKind.ALWAYS_ALLOWED,
        engine_pb2.PlanResourcesFilter.KIND_ALWAYS_ALLOWED,
    ]
)


def create_lookup_from_attribute(attr: GenericAttribute) -> str:
    if isinstance(attr, str):
        lookup = attr
    elif isinstance(attr, Field):
        lookup = attr.name
    elif isinstance(attr, DeferredAttribute):
        lookup = create_lookup_from_attribute(attr.field)
    elif isinstance(attr, ForwardManyToOneDescriptor):
        lookup = create_lookup_from_attribute(attr.field)
    # ManyToManyDescriptor is a subclass of ReverseManyToOneDescriptor -> needs to be checked first
    elif isinstance(attr, ManyToManyDescriptor):
        if attr.reverse:
            relation: ManyToManyRel = attr.rel
            lookup = relation.related_name
        else:
            lookup = create_lookup_from_attribute(attr.field)
    elif isinstance(attr, ReverseManyToOneDescriptor):
        relation: ManyToOneRel = attr.rel
        lookup = relation.related_name
    elif isinstance(attr, Iterable):
        lookup = "__".join([create_lookup_from_attribute(element) for element in attr])
    else:
        raise ValueError(f"Attribute {attr} cannot be resolved into a valid lookup.")
    return lookup


def get_query(
    query_plan: Union[PlanResourcesResponse, response_pb2.PlanResourcesResponse],
    attr_map: Dict[str, GenericAttribute],
    operator_override_fns: Optional[OperatorFnMap] = None,
) -> Q:
    if query_plan.filter is None or query_plan.filter.kind in _deny_types:
        return Q(pk__in=[])  # Doesn't hit DB

    if query_plan.filter.kind in _allow_types:
        return Q()

    def get_operator_fn(op: str, c: str, v: Any) -> Q:
        # Check to see if the client has overridden the function
        if (
            operator_override_fns
            and (override_fn := operator_override_fns.get(op)) is not None
        ):
            return override_fn(c, v)

        # Otherwise, fall back to default handlers
        if (default_fn := OPERATOR_FNS.get(op)) is not None:
            return default_fn(c, v)

        raise ValueError(f"Unrecognised operator: {op}")

    def traverse_and_map_operands(operand: dict) -> Q:
        if exp := operand.get("expression"):
            return traverse_and_map_operands(exp)

        operator = operand["operator"]
        child_operands = operand["operands"]

        # if `operator` in ["and", "or"], `child_operands` is a nested list of `expression` dicts (handled at the
        # beginning of this closure)
        if operator == "and":
            return reduce(and_, (traverse_and_map_operands(o) for o in child_operands))
        if operator == "or":
            return reduce(or_, (traverse_and_map_operands(o) for o in child_operands))
        if operator == "not":
            return ~(reduce(and_, (traverse_and_map_operands(o) for o in child_operands)))

        # otherwise, they are a list[dict] (len==2), in the form: `[{'variable': 'foo'}, {'value': 'bar'}]`
        # The order of the keys `variable` and `value` is not guaranteed.
        d = {k: v for o in child_operands for k, v in o.items()}
        variable = d["variable"]
        value = d["value"]

        try:
            attribute = attr_map[variable]
        except KeyError:
            raise KeyError(
                f"Attribute does not exist in the attribute column map: {variable}"
            )

        attribute_lookup = create_lookup_from_attribute(attribute)

        # the operator handlers here are the leaf nodes of the recursion
        return get_operator_fn(operator, attribute_lookup, value)

    cond = (
        MessageToDict(query_plan.filter.condition)
        if isinstance(query_plan, response_pb2.PlanResourcesResponse)
        else cast(DataClassJsonMixin, query_plan.filter.condition).to_dict()
    )

    return traverse_and_map_operands(cond)
