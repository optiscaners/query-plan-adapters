import os
from contextlib import contextmanager

import pytest
from cerbos.engine.v1 import engine_pb2
from cerbos.sdk.client import CerbosClient
from cerbos.sdk.container import CerbosContainer as _CerbosContainer
from cerbos.sdk.grpc.client import CerbosClient as GrpcCerbosClient
from cerbos.sdk.model import Principal, ResourceDesc

from testproject.testapp import models

USER_ROLE = "USER"


@pytest.fixture
def testdata(transactional_db) -> None:
    user_1 = models.User(id=1, name="user1", role="admin")
    user_2 = models.User(id=2, name="user2", role="user")
    models.User.objects.bulk_create([user_1, user_2])

    nested_1 = models.NestedResource(
        id=1,
        aString="string1",
        aNumber=1,
        aBool=True,
    )
    nested_2 = models.NestedResource(
        id=2,
        aString="string2",
        aNumber=2,
        aBool=False,
    )
    models.NestedResource.objects.bulk_create([nested_1, nested_2])

    resource_1 = models.Resource(
        name="resource1",
        aBool=True,
        aString="string",
        aNumber=1,
        ownedBy_id=1,
        createdBy_id=1,
        nested_id=1,
    )
    resource_2 = models.Resource(
        name="resource2",
        aBool=False,
        aString="amIAString?",
        aNumber=2,
        ownedBy_id=1,
        createdBy_id=2,
        nested_id=1,
    )
    resource_3 = models.Resource(
        name="resource3",
        aBool=True,
        aString="anotherString",
        aNumber=3,
        ownedBy_id=2,
        createdBy_id=2,
        nested_id=2,
    )
    models.Resource.objects.bulk_create([resource_1, resource_2, resource_3])

    user_1.related.add(nested_1)
    user_2.related.add(nested_2)

    resource_1.related.add(nested_1)
    resource_2.related.add(nested_1, nested_2)
    resource_3.related.add(nested_2)


@pytest.fixture
def user_model():
    return models.User


@pytest.fixture
def resource_model():
    return models.Resource


@pytest.fixture
def nested_resource_model():
    return models.NestedResource


# Workaround for Windows 10 -> localnpipe needs to be translated to localhost
#  https://github.com/testcontainers/testcontainers-python/issues/108#issuecomment-660371568
if os.name == "nt":
    class CerbosContainer(_CerbosContainer):
        def get_container_host_ip(self) -> str:
            host = super().get_container_host_ip()
            if host == "localnpipe":
                host = "localhost"
            return host

else:
    CerbosContainer = _CerbosContainer


@contextmanager
def cerbos_container_host(client_type: str) -> str:
    policy_dir = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "../..", "policies")
    )

    container = CerbosContainer(image="ghcr.io/cerbos/cerbos:dev")
    container.with_volume_mapping(policy_dir, "/policies")
    container.with_env("CERBOS_NO_TELEMETRY", "1")
    container.with_command("server --set=schema.enforcement=reject")
    container.start()
    container.wait_until_ready()

    yield container.http_host() if client_type == "http" else container.grpc_host()

    container.stop()


@pytest.fixture(scope="module", params=["http", "grpc"])
def cerbos_client(request):
    client_type = request.param
    with cerbos_container_host(client_type) as host:
        client_cls = CerbosClient if client_type == "http" else GrpcCerbosClient
        with client_cls(host, tls_verify=False) as client:
            yield client


@pytest.fixture
def principal(cerbos_client):
    principal_cls = (
        engine_pb2.Principal
        if isinstance(cerbos_client, GrpcCerbosClient)
        else Principal
    )
    return principal_cls(id="1", roles={USER_ROLE})


@pytest.fixture
def resource_desc(cerbos_client):
    desc_cls = (
        engine_pb2.PlanResourcesInput.Resource
        if isinstance(cerbos_client, GrpcCerbosClient)
        else ResourceDesc
    )
    return desc_cls(kind="resource")
