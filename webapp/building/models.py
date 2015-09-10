from django.db import models

from server.engine.models.building import properties_schema
from utils.models import JSONField


class Building(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    build_time = models.IntegerField(help_text='in seconds for default speed')
    cost_money = models.IntegerField()
    cost_population = models.IntegerField()
    properties = JSONField(schema=properties_schema)

    def __str__(self):
        return self.name
