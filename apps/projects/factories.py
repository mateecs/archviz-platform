# apps/projects/factories.py
import factory

from apps.accounts.models import User
#from .models import Project
from apps.projects.models import Project


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    role = User.Role.CLIENT


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    client = factory.SubFactory(UserFactory, role=User.Role.CLIENT)
    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph")
    project_type = Project.ProjectType.EXTERIOR