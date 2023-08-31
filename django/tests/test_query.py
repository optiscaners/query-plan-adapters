import pytest
from cerbos.sdk.model import (
    PlanResourcesFilter,
    PlanResourcesFilterKind,
    PlanResourcesResponse,
)
from django.db.models import Q

from cerbos_django import get_query
from cerbos_django.query import create_lookup_from_attribute


def _default_resp_params():
    return {
        "request_id": "1",
        "action": "action",
        "resource_kind": "resource",
        "policy_version": "default",
    }


class TestGetQuery:
    def test_always_allow(
        self, cerbos_client, principal, resource_desc, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("always-allow", principal, resource_desc)
        qs = resource_model.objects.filter(get_query(plan, {}))
        res = qs.all()
        assert len(res) == 3

    def test_always_deny(
        self, cerbos_client, principal, resource_desc, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("always-deny", principal, resource_desc)
        qs = resource_model.objects.filter(get_query(plan, {}))
        res = qs.all()
        assert len(res) == 0

    def test_equals(
        self, cerbos_client, principal, resource_desc, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("equal", principal, resource_desc)
        attr = {
            "request.resource.attr.aBool": resource_model.aBool,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource3"}, res))

    def test_not_equals(
        self, cerbos_client, principal, resource_desc, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("ne", principal, resource_desc)
        attr = {
            "request.resource.attr.aString": resource_model.aString,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource2", "resource3"}, res))

    def test_and(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("and", principal, resource_desc)
        attr = {
            "request.resource.attr.aBool": resource_model.aBool,
            "request.resource.attr.aString": resource_model.aString,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 1
        assert res[0].name == "resource3"

    def test_not_and(
        self, cerbos_client, principal, resource_desc, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("nand", principal, resource_desc)
        attr = {
            "request.resource.attr.aBool": resource_model.aBool,
            "request.resource.attr.aString": resource_model.aString,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource2"}, res))

    def test_or(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("or", principal, resource_desc)
        attr = {
            "request.resource.attr.aBool": resource_model.aBool,
            "request.resource.attr.aString": resource_model.aString,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 3

    def test_not_or(
        self, cerbos_client, principal, resource_desc, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("nor", principal, resource_desc)
        attr = {
            "request.resource.attr.aBool": resource_model.aBool,
            "request.resource.attr.aString": resource_model.aString,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 0

    def test_in(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("in", principal, resource_desc)
        attr = {
            "request.resource.attr.aString": resource_model.aString,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource3"}, res))

    def test_lt(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("lt", principal, resource_desc)
        attr = {
            "request.resource.attr.aNumber": resource_model.aNumber,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 1
        assert res[0].name == "resource1"

    def test_gt(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("gt", principal, resource_desc)
        attr = {
            "request.resource.attr.aNumber": resource_model.aNumber,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource2", "resource3"}, res))

    def test_lte(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("lte", principal, resource_desc)
        attr = {
            "request.resource.attr.aNumber": resource_model.aNumber,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource2"}, res))

    def test_gte(self, cerbos_client, principal, resource_desc, resource_model, testdata):
        plan = cerbos_client.plan_resources("gte", principal, resource_desc)
        attr = {
            "request.resource.attr.aNumber": resource_model.aNumber,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 3

    def test_relation_some(
        self, cerbos_client, principal, resource_desc, user_model, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("relation-some", principal, resource_desc)
        attr = {
            "request.resource.attr.ownedBy": resource_model.ownedBy,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource2"}, res))

    def test_relation_none(
        self, cerbos_client, principal, resource_desc, user_model, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("relation-none", principal, resource_desc)
        attr = {
            "request.resource.attr.ownedBy": resource_model.ownedBy,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 1
        assert res[0].name == "resource3"

    def test_relation_is(
        self, cerbos_client, principal, resource_desc, user_model, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("relation-is", principal, resource_desc)
        attr = {
            "request.resource.attr.createdBy": resource_model.createdBy,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 1
        assert res[0].name == "resource1"

    def test_relation_is_not(
        self, cerbos_client, principal, resource_desc, user_model, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("relation-is-not", principal, resource_desc)
        attr = {
            "request.resource.attr.createdBy": resource_model.createdBy,
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource2", "resource3"}, res))

    def test_relation_equal_nested_explicit_lookup(
        self, cerbos_client, principal, resource_desc, user_model, resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("equal-nested", principal, resource_desc)
        attr = {
            "request.resource.attr.nested.aBool": "nested__aBool",
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource2"}, res))

    def test_relation_equal_nested_implicit_lookup_through_field_chain(
        self, cerbos_client, principal, resource_desc, user_model, resource_model, nested_resource_model, testdata
    ):
        plan = cerbos_client.plan_resources("equal-nested", principal, resource_desc)
        attr = {
            "request.resource.attr.nested.aBool": [
                resource_model.nested,
                nested_resource_model.aBool,

            ],
        }
        qs = resource_model.objects.filter(get_query(plan, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource2"}, res))


class TestCreateLookupFromAttribute:
    def test_deferred_attribute(self, resource_model):
        lookup = create_lookup_from_attribute(resource_model.name)
        assert lookup == "name"

    def test_forward_many_to_one_relation(self, resource_model):
        lookup = create_lookup_from_attribute(resource_model.nested)
        assert lookup == "nested"

    def test_reverse_many_to_one_relation(self, nested_resource_model):
        lookup = create_lookup_from_attribute(nested_resource_model.resources)
        assert lookup == "resources"

    def test_many_to_many_relation(self, resource_model):
        lookup = create_lookup_from_attribute(resource_model.nested_m2m)
        assert lookup == "nested_m2m"

    def test_reverse_many_to_many_relation(self, nested_resource_model):
        lookup = create_lookup_from_attribute(nested_resource_model.resources_m2m)
        assert lookup == "resources_m2m"

    def test_chained_lookup(self, resource_model, nested_resource_model):
        lookup = create_lookup_from_attribute([
            resource_model.nested,
            nested_resource_model.aBool,
        ])
        assert lookup == "nested__aBool"

    def test_triple_chained_lookup(self, user_model, resource_model, nested_resource_model):
        lookup = create_lookup_from_attribute([
            user_model.owned_resources,
            resource_model.nested,
            nested_resource_model.aBool,
        ])
        assert lookup == "owned_resources__nested__aBool"


class TestGetQueryOverrides:
    def test_in_single_query(self, resource_model, testdata):
        plan_resources_filter = PlanResourcesFilter.from_dict(
            {
                "kind": PlanResourcesFilterKind.CONDITIONAL,
                "condition": {
                    "expression": {
                        "operator": "in",
                        "operands": [
                            {"variable": "request.resource.attr.name"},
                            {"value": "resource1"},
                        ],
                    },
                },
            }
        )
        plan_resource_resp = PlanResourcesResponse(
            filter=plan_resources_filter,
            **_default_resp_params(),
        )
        attr = {
            "request.resource.attr.name": resource_model.name,
        }
        qs = resource_model.objects.filter(get_query(plan_resource_resp, attr))
        res = qs.all()
        assert len(res) == 1
        assert res[0].name == "resource1"

    def test_in_multiple_query(self, resource_model, testdata):
        plan_resources_filter = PlanResourcesFilter.from_dict(
            {
                "kind": PlanResourcesFilterKind.CONDITIONAL,
                "condition": {
                    "expression": {
                        "operator": "in",
                        "operands": [
                            {"variable": "request.resource.attr.name"},
                            {"value": ["resource1", "resource2"]},
                        ],
                    },
                },
            }
        )
        plan_resource_resp = PlanResourcesResponse(
            filter=plan_resources_filter,
            **_default_resp_params(),
        )
        attr = {
            "request.resource.attr.name": resource_model.name,
        }
        qs = resource_model.objects.filter(get_query(plan_resource_resp, attr))
        res = qs.all()
        assert len(res) == 2
        assert all(map(lambda x: x.name in {"resource1", "resource2"}, res))

    def test_unrecognised_response_attribute(self, resource_model):
        unknown_attribute = "request.resource.attr.foo"
        plan_resources_filter = PlanResourcesFilter.from_dict(
            {
                "kind": PlanResourcesFilterKind.CONDITIONAL,
                "condition": {
                    "expression": {
                        "operator": "eq",
                        "operands": [
                            {"variable": unknown_attribute},
                            {"value": 1},
                        ],
                    },
                },
            }
        )
        plan_resource_resp = PlanResourcesResponse(
            filter=plan_resources_filter,
            **_default_resp_params(),
        )
        attr = {
            "request.resource.attr.ownedBy": resource_model.ownedBy,
        }
        with pytest.raises(KeyError) as exc_info:
            get_query(plan_resource_resp, attr)
        assert (
            exc_info.value.args[0]
            == f"Attribute does not exist in the attribute column map: {unknown_attribute}"
        )

    def test_unrecognised_filter(self, resource_model):
        unknown_op = "unknown"
        plan_resources_filter = PlanResourcesFilter.from_dict(
            {
                "kind": PlanResourcesFilterKind.CONDITIONAL,
                "condition": {
                    "expression": {
                        "operator": unknown_op,
                        "operands": [
                            {"variable": "request.resource.attr.ownedBy"},
                            {"value": "1"},
                        ],
                    },
                },
            }
        )
        plan_resource_resp = PlanResourcesResponse(
            filter=plan_resources_filter,
            **_default_resp_params(),
        )
        attr = {
            "request.resource.attr.ownedBy": resource_model.ownedBy,
        }
        with pytest.raises(ValueError) as exc_info:
            get_query(plan_resource_resp, attr)
        assert exc_info.value.args[0] == f"Unrecognised operator: {unknown_op}"

    def test_in_equals_override(self, resource_model, testdata):
        plan_resources_filter = PlanResourcesFilter.from_dict(
            {
                "kind": PlanResourcesFilterKind.CONDITIONAL,
                "condition": {
                    "expression": {
                        "operator": "in",
                        "operands": [
                            {"variable": "request.resource.attr.name"},
                            {"value": "resource1"},
                        ],
                    },
                },
            }
        )
        plan_resource_resp = PlanResourcesResponse(
            filter=plan_resources_filter,
            **_default_resp_params(),
        )
        attr = {
            "request.resource.attr.name": resource_model.name,
        }
        operator_override_fns = {
            "in": lambda c, v: Q(**{c: v}),
        }
        qs = resource_model.objects.filter(
            get_query(
                plan_resource_resp,
                attr,
                operator_override_fns=operator_override_fns,
            )
        )
        res = qs.all()
        assert len(res) == 1
        assert res[0].name == "resource1"
