# Cerbos + Django Adapter

> This adapter was created based on the sqlalchemy adapter and translated for django querysets.

An adapter library that takes a [Cerbos](https://cerbos.dev) Query
Plan ([PlanResources API](https://docs.cerbos.dev/cerbos/latest/api/index.html#resources-query-plan)) response and
converts it into a [django](https://djangoproject.com) `QuerySet`. This is designed to work alongside a project using
the [Cerbos Python SDK](https://github.com/cerbos/cerbos-sdk-python).

The following conditions are supported:

| Operator | Supported | Remarks                                                                |
|---------:|:----------|------------------------------------------------------------------------|
|    `and` | yes       |                                                                        |
|     `or` | yes       |                                                                        |
|    `not` | yes       |                                                                        |
|     `eq` | yes       |                                                                        |
|     `ne` | yes       |                                                                        |
|     `lt` | yes       |                                                                        |
|     `gt` | yes       |                                                                        |
|     `le` | yes       | `lte` in django                                                        |
|     `ge` | yes       | `gte` in django                                                        |
|     `in` | yes       |                                                                        |
| `exists` | partially | Statements inside `.exists(...)` cannot depend on resource attributes. |

## Requirements

- Cerbos > v0.16
- Django >= 3.2

## Installation

For now:

```
pip install git+ssh://git@github.com/optiscaners/query-plan-adapters@django#subdirectory=django
```

In the future:

```
pip install cerbos_django
```

## Usage

```python
from cerbos.sdk.client import CerbosClient
from cerbos.sdk.model import Principal, ResourceDesc

from cerbos_django import get_query
from django.db import models


class LeaveRequest(models.Model):
    id = models.BigAutoField(primary_key=True)
    department = models.CharField(max_length=255)
    geography = models.CharField(max_length=255)
    team = models.CharField(max_length=255)
    priority = models.IntegerField()


with CerbosClient(host="http://localhost:3592") as c:
    p = Principal(
        "john",
        roles={"employee"},
        policy_version="20210210",
        attr={"department": "marketing", "geography": "GB", "team": "design"},
    )

    # Get the query plan for "view" action
    rd = ResourceDesc("leave_request", policy_version="20210210")
    plan = c.plan_resources("view", p, rd)

# the attr_map arg of get_queryset expects a map with cerbos attribute strings mapped to the field lookup (str) or model-attribute
attr_map = {
    "request.resource.attr.department": LeaveRequest.department,  # "department" is also allowed
    "request.resource.attr.geography": LeaveRequest.geography,
    "request.resource.attr.team": LeaveRequest.team,
    "request.resource.attr.priority": LeaveRequest.priority,
}

queryset: models.QuerySet[LeaveRequest] = LeaveRequest.objects.filter(get_query(plan, attr_map))

# optionally extend the query
queryset = queryset.filter(priority__lt=5)

# or return a subset of the selected fields (via `only`)
queryset = queryset.only(
    "department",
    "geography",
)

# Print the compiled query (for debug purposes)
print(queryset.query)
```

### Related resources

When working with related models (`ForeignKey`, `OneToOneField`, `ManyToManyField`) nested lookups can be required.
In this case, the map between cerbos resource attribute and django lookup can be defined

* explicitly (`"employee__name"`)
* or implicitly from chaining the lookup path as a list of model attributes (`[LeaveRequest.employee, Employee.name]`)

```python
class Employee(models.Model):
    name = models.CharField(max_length=255)


class LeaveRequest(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)


queryset: models.QuerySet[LeaveRequest] = LeaveRequest.objects.filter(
    get_query(
        plan,
        {
            "request.resource.attr.employee.name": [LeaveRequest.employee, Employee.name],  # or "employee__name"
        },
    )
)

```

### Resource and principal with common relation

When working with related models that are also related to the principal, it can be necessary to determine if they share
the same related objects.
This can be done by using the `in` or `exists` operator. If the resource attribute is a single element use `in`, if it's
a collection of elements use `exists`.

Be careful to formulate the conditions such that the resource attributes are put on the left side.
That way, the operations requiring principal attributes are simplified before constructing the AST, which prevents
complex operators (like `set-field`, `get-field`, `struct`) from being used which are not supported by this package.
This is also considered
a [best-practice](https://docs.cerbos.dev/cerbos/latest/policies/best_practices#_map_of_relations) when working with
relations.

Note: `exists` is only supported when it doesn't depend on resource attributes and the statement inside brackets can be
simplified to constants.
(Supported: `R.attr.foo.exists(x, x in V.bar)`, not supported: `V.bar.exists(x, x in R.attr.foo)`)

```yaml
# Only resources that are owned by the principal 
condition:
  match:
    expr: R.id in P.attr.relations.filter(x, P.attr.relations[x] == "owner")

# Only resources that are part of a group, where the principal is also an owner (two unrelated many-to-many fields)
condition:
  match:
    expr: R.attr.relatedGroups.exists(x, x in P.attr.relatedGroups.filter(y, P.attr.relatedGroups[y].role == "owner")) 
```

### Overriding default predicates

By default, the library provides a base set of operators. However, in some cases, users may wish to override or add a
particular operator.

```python
from typing import cast, Any, Callable, Dict

from django.db.models import Q

OperatorFunction = Dict[str, Callable[[str, Any], Q]]

queryset = SomeModel.objects.filter(
    get_query(
        plan_resource_resp,
        attr_map={
            "request.resource.attr.foo": SomeModel.foo,
        },
        # override handler functions in the map below
        operator_override_fns=cast(
            OperatorFunction,
            {
                "in": lambda c, v: Q(**{c + "__icontains": v}),
            }
        ),
    )
)
```
