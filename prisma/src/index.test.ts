import { queryPlanToPrisma, PlanKind } from ".";
import { PlanExpression, PlanResourcesConditionalResponse } from "@cerbos/core";
import { Prisma, PrismaClient } from '@prisma/client'
import { GRPC as Cerbos } from "@cerbos/grpc";

const prisma = new PrismaClient()
const cerbos = new Cerbos("127.0.0.1:3593", { tls: false })

const fixtureUsers: Prisma.UserCreateInput[] = [{
  id: "user1",
  aBool: true,
  aNumber: 1,
  aString: "string"
},
{
  id: "user2",
  aBool: true,
  aNumber: 2,
  aString: "string"
}]

const fixtureResources: Prisma.ResourceCreateInput[] = [
  {
    id: "resource1",
    aBool: true,
    aNumber: 1,
    aString: "string",
    owners: {
      connect: [{
        id: "user1"
      }]
    }
  },
  {
    id: "resource2",
    aBool: false,
    aNumber: 2,
    aString: "string2",
    owners: {
      connect: [{
        id: "user2"
      }]
    }
  },
  {
    id: "resource3",
    aBool: false,
    aNumber: 3,
    aString: "string3",
    owners: {
      connect: [{
        id: "user1"
      }, {
        id: "user2"
      }]
    }
  }
]

beforeAll(async () => {
  await prisma.resource.deleteMany();
  await prisma.user.deleteMany();
})

beforeEach(async () => {
  for (const user of fixtureUsers) {
    await prisma.user.create({ data: user })
  }
  for (const resource of fixtureResources) {
    await prisma.resource.create({ data: resource })
  }
});

afterEach(async () => {
  await prisma.resource.deleteMany();
  await prisma.user.deleteMany();
});


test("always allowed", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "always-allow"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {},
  });

  expect(result).toStrictEqual({
    kind: PlanKind.ALWAYS_ALLOWED,
    filters: {}
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query.length).toEqual(fixtureResources.length)
});

test("always denied", async () => {

  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "always-deny"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {},
  });

  expect(result).toStrictEqual({
    kind: PlanKind.ALWAYS_DENIED
  });
});


test("conditional - eq", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "equal"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aBool": "aBool",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: { aBool: { equals: true } }
  });
  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(a => a.aBool).map(f => ({ ...f, owners: undefined })))
});

test("conditional - eq - inverted order", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "equal"
  })
  const typeQp = (queryPlan as PlanResourcesConditionalResponse);

  const invertedQueryPlan: PlanResourcesConditionalResponse = {
    ...typeQp,
    condition: {
      ...typeQp.condition,
      operands: [
        (typeQp.condition as PlanExpression).operands[1],
        (typeQp.condition as PlanExpression).operands[0],
      ]
    }
  }

  const result = queryPlanToPrisma({
    queryPlan: invertedQueryPlan,
    fieldNameMapper: {
      "request.resource.attr.aBool": "aBool",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: { aBool: { equals: true } }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(a => a.aBool).map(f => ({ ...f, owners: undefined })))
});


test("conditional - ne", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "ne"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aString": "aString",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: { aString: { not: "string" } }
  });
  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(a => a.aString != "string").map(f => ({ ...f, owners: undefined })))
});


test("conditional - explicit-deny", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "explicit-deny"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aBool": "aBool",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: { NOT: { aBool: { equals: true } } }
  });
  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(a => !a.aBool).map(f => ({ ...f, owners: undefined })))
});

test("conditional - and", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "and"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aBool": "aBool",
      "request.resource.attr.aString": "aString",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      AND: [
        {
          aBool: { equals: true }
        },
        {
          aString: { not: "string" }
        }
      ]
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return r.aBool && r.aString != "string"
  }).map(f => ({ ...f, owners: undefined })))
});



test("conditional - or", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "or"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aBool": "aBool",
      "request.resource.attr.aString": "aString",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      OR: [
        {
          aBool: { equals: true }
        },
        {
          aString: { not: "string" }
        }
      ]
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return r.aBool || r.aString != "string"
  }).map(f => ({ ...f, owners: undefined })))
});

test("conditional - in", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "in"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aString": "aString",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      aString: { in: ["string", "anotherString"] }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return ["string", "anotherString"].includes(r.aString)
  }).map(f => ({ ...f, owners: undefined })))
});


test("conditional - gt", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "gt"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aNumber": "aNumber",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      aNumber: { gt: 1 }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return r.aNumber > 1
  }).map(f => ({ ...f, owners: undefined })))
});

test("conditional - lt", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "lt"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aNumber": "aNumber",
    },
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      aNumber: { lt: 2 }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return r.aNumber < 2
  }).map(f => ({ ...f, owners: undefined })))
});


test("conditional - gte", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "gte"
  })


  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aNumber": "aNumber",
    },
  });


  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      aNumber: { gte: 1 }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return r.aNumber >= 1
  }).map(f => ({ ...f, owners: undefined })))
});

test("conditional - lte", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "lte"
  })


  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {
      "request.resource.attr.aNumber": "aNumber",
    },
  });


  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      aNumber: { lte: 2 }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })
  expect(query).toEqual(fixtureResources.filter(r => {
    return r.aNumber <= 2
  }).map(f => ({ ...f, owners: undefined })))
});





test("conditional - relation some", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "relation-some"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {},
    relationMapper: {
      "request.resource.attr.owners": {
        "relation": "owners",
        "field": "id"
      }
    }
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      owners: {
        some: {
          id: "user1"
        }
      }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })

  expect(query).toEqual(fixtureResources.filter(r => {
    if (!r.owners?.connect) return false;
    return (r.owners.connect as { id: string }[]).filter(o => o.id == "user1").length > 0
  }).map(f => ({ ...f, owners: undefined })))
});



test("conditional - relation none", async () => {
  const queryPlan = await cerbos.planResources({
    principal: { id: "user1", roles: ["USER"] },
    resource: { kind: "resource" },
    action: "relation-none"
  })

  const result = queryPlanToPrisma({
    queryPlan,
    fieldNameMapper: {},
    relationMapper: {
      "request.resource.attr.owners": {
        "relation": "owners",
        "field": "id"
      }
    }
  });

  expect(result).toStrictEqual({
    kind: PlanKind.CONDITIONAL,
    filters: {
      NOT: {
        owners: {
          some: {
            id: "user1"
          }
        }
      }
    }
  });

  const query = await prisma.resource.findMany({ where: { ...result.filters } })

  expect(query).toEqual(fixtureResources.filter(r => {
    if (!r.owners?.connect) return false;
    return (r.owners.connect as { id: string }[]).filter(o => o.id == "user1").length == 0
  }).map(f => ({ ...f, owners: undefined })))
});

