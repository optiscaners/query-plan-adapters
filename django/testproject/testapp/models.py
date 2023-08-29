from django.db import models


# Create your models here.
class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=30)
    role = models.CharField(
        max_length=10,
        choices=[
            ("admin", "Admin user"),
            ("user", "Normal user"),
        ],
    )


class Resource(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=30)
    # Camel case, as we're being consistent with the attributes created in the base policy files for the shared repo
    aBool = models.BooleanField()
    aString = models.TextField()
    aNumber = models.IntegerField()

    ownedBy = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_resources")
    createdBy = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_resources")
    nested = models.ForeignKey("NestedResource", on_delete=models.CASCADE, related_name="resources")

    nested_m2m = models.ManyToManyField("NestedResource", related_name="resources_m2m", null=True)
    nested_o2o = models.OneToOneField(
        "NestedResource",
        related_name="resource_o2o",
        on_delete=models.CASCADE,
        null=True,
    )


class NestedResource(models.Model):
    id = models.BigAutoField(primary_key=True)
    aString = models.CharField(max_length=30)
    aNumber = models.IntegerField()
    aBool = models.BooleanField()
