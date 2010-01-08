from django.db import models
from django.core.urlresolvers import reverse as reverse_url
from publish.models import Publishable

class Page(Publishable):
    title = models.CharField(max_length=200)
    slug  = models.CharField(max_length=100, db_index=True)
    
    parent = models.ForeignKey('self', blank=True, null=True)

    categories = models.ManyToManyField('Category', blank=True)

    def __unicode__(self):
        return self.title

    def _get_all_slugs(self):
        slugs = []
        if self.parent:
            slugs.extend(self.parent._get_all_slugs())
        slugs.append(self.slug)
        return slugs

    def get_absolute_url(self):
        url = '/'.join(self._get_all_slugs())
        if self.is_public:
            return reverse_url('public_page_detail', args=[url])
        else:
            return reverse_url('draft_page_detail', args=[url])

class PageBlock(Publishable):
    page = models.ForeignKey(Page)
    content = models.TextField(blank=False)

class Category(Publishable):
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=100, db_index=True)

    def __unicode__(self):
        return self.name
