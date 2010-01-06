from django.db import models
from publish.models import Publishable

class Page(Publishable):
    title = models.CharField(max_length=200)
    slug  = models.CharField(max_length=100, db_index=True)
    content = models.TextField(blank=True)
    
    parent = models.ForeignKey('self', blank=True, null=True)

    def __unicode__(self):
        return self.title
