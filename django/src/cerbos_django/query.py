from types import MappingProxyType
from typing import Any, Callable, cast, TypeVar

from cerbos.engine.v1 import engine_pb2
from cerbos.response.v1 import response_pb2
from cerbos.sdk.model import PlanResourcesFilterKind, PlanResourcesResponse
from dataclasses_json import DataClassJsonMixin
from django.db.models import Field, Model as _Model, QuerySet, Q, ForeignKey
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor
from django.db.models.query_utils import DeferredAttribute
from google.protobuf.json_format import MessageToDict

Model = TypeVar("Model", bound=_Model)
OperatorFnMap = dict[str, Callable[[str, Any], Q]]
GenericExpression = Any

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


def get_queryset(
    query_plan: PlanResourcesResponse | response_pb2.PlanResourcesResponse,
    model: type[Model],
    attr_map: dict[str, DeferredAttribute],
    model_mapping: list[tuple[type[Model], GenericExpression]] | None = None,
    operator_override_fns: OperatorFnMap | None = None,
) -> QuerySet[Model]:
    if query_plan.filter is None or query_plan.filter.kind in _deny_types:
        return model.objects.none()

    if query_plan.filter.kind in _allow_types:
        return model.objects.all()

    # Inspect passed columns. If > 1 origin table, assert that the mapping has been defined
    required_tables = set()
    for c in attr_map.values():
        # c is of type Column | InstrumentedAttribute - both have a `table` attribute returning a `Table` type
        field: Field = c.field
        if (n := field.model) != model:
            required_tables.add(n)

    if len(required_tables):
        if model_mapping is None:
            raise TypeError(
                "get_query() missing 1 required positional argument: 'model_mapping'"
            )
        for m, _ in model_mapping:
            required_tables.discard(m)
        if len(required_tables):
            raise TypeError(
                "positional argument 'model_mapping' missing mapping for table(s): '{0}'".format(
                    "', '".join(required_tables)
                )
            )

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
            return Q(*[traverse_and_map_operands(o) for o in child_operands])
        if operator == "or":
            op = Q()
            for o in child_operands:
                op |= traverse_and_map_operands(o)
            return op
        if operator == "not":
            return ~Q(*[traverse_and_map_operands(o) for o in child_operands])

        # otherwise, they are a list[dict] (len==2), in the form: `[{'variable': 'foo'}, {'value': 'bar'}]`
        # The order of the keys `variable` and `value` is not guaranteed.
        d = {k: v for o in child_operands for k, v in o.items()}
        variable = d["variable"]
        value = d["value"]

        try:
            attribute = attr_map[variable]
            # Field
            if isinstance(attribute, DeferredAttribute):
                lookup = cast(Field, attribute.field).name
            elif isinstance(attribute, ForwardManyToOneDescriptor):
                fk_field = cast(ForeignKey, attribute.field)
                lookup = "__".join([fk_field.name, cast(Field, fk_field.target_field).name])
            elif isinstance(attribute, Field):
                lookup = attribute.name
            else:
                raise ValueError(f"Attribute {variable} cannot be resolved into a valid lookup.")
        except KeyError:
            raise KeyError(
                f"Attribute does not exist in the attribute column map: {variable}"
            )

        # the operator handlers here are the leaf nodes of the recursion
        return get_operator_fn(operator, lookup, value)

    cond = (
        MessageToDict(query_plan.filter.condition)
        if isinstance(query_plan, response_pb2.PlanResourcesResponse)
        else cast(DataClassJsonMixin, query_plan.filter.condition).to_dict()
    )

    query = traverse_and_map_operands(cond)
    q = model.objects.filter(query)

    # if table_mapping:
    #     q = q.select_from(table)
    #     for join_table, predicate in table_mapping:
    #         q = q.join(join_table, predicate)

    return q
