from django.db import models
from django.db.models.query import QuerySet, Q
from django.conf import settings
from django.db.models.fields.related import RelatedField

from utils import NestedSet

# this takes some inspiration from the publisher stuff in
# django-cms 2.0
# e.g. http://github.com/digi604/django-cms-2.0/blob/master/publisher/models.py
#
# but we want this to be a reusable/standalone app and have a few different needs
#

class PublishableQuerySet(QuerySet):

    def changed(self):
        '''all draft objects that have not been published yet'''
        return self.filter(is_public=False, publish_state=Publishable.PUBLISH_CHANGED)
    
    def deleted(self):
        '''public objects that need deleting'''
        return self.filter(is_public=True, publish_state=Publishable.PUBLISH_DELETE)

    def draft(self):
        '''all draft objects'''
        return self.filter(is_public=False)
   
    def draft_and_deleted(self):
        return self.filter(Q(is_public=False) | Q(is_public=True, publish_state=Publishable.PUBLISH_DELETE))
 
    def published(self):
        '''all public/published objects'''
        return self.filter(is_public=True)

    def publish(self):
        '''publish all models in this queryset and return a list of the published versions'''
        for p in self:
            p.publish()
    
    def delete(self):
        '''
        override delete so that we call delete on each object separately, as delete needs
        to set some flags etc
        '''
        for p in self:
            p.delete()


class PublishableManager(models.Manager):
    
    def get_query_set(self):
        return PublishableQuerySet(self.model)

    def changed(self):
        '''all draft objects that have not been published yet'''
        return self.get_query_set().changed()
        
    def deleted(self):
        '''public objects that need deleting'''
        return self.get_query_set().deleted()
    
    def draft(self):
        '''all draft objects'''
        return self.get_query_set().draft()
    
    def draft_and_deleted(self):
        return self.get_query_set().draft_and_deleted()   
 
    def published(self):
        '''all public/published objects'''
        return self.get_query_set().published()

class Publishable(models.Model):
    PUBLISH_DEFAULT = 0
    PUBLISH_CHANGED = 1
    PUBLISH_DELETE  = 2

    PUBLISH_CHOICES = ((PUBLISH_DEFAULT, ''), (PUBLISH_CHANGED, 'Changed'), (PUBLISH_DELETE, 'To be deleted'))

    is_public = models.BooleanField(default=False, editable=False, db_index=True)
    publish_state = models.IntegerField('Publication status', editable=False, db_index=True, choices=PUBLISH_CHOICES, default=PUBLISH_DEFAULT)
    public = models.OneToOneField('self', related_name='draft', null=True, editable=False)
    
    class Meta:
        abstract = True

    class PublishMeta(object):
        publish_exclude_fields = ['id', 'is_public', 'publish_state', 'public', 'draft']
        publish_reverse_fields = []

        @classmethod
        def _combined_fields(cls, field_name):
            fields = []
            for clazz in cls.__mro__:
                fields.extend(getattr(clazz, field_name, []))
            return fields

        @classmethod
        def excluded_fields(cls):
            return cls._combined_fields('publish_exclude_fields')

        @classmethod
        def reverse_fields_to_publish(cls):
            return cls._combined_fields('publish_reverse_fields')

    objects = PublishableManager()

    def save(self, mark_changed=True, *arg, **kw):
        if not self.is_public and mark_changed:
            self.publish_state = Publishable.PUBLISH_CHANGED
        super(Publishable, self).save(*arg, **kw)
    
    def delete(self):
        if self.public:
            # mark public version for future deletion
            self.public.publish_state = Publishable.PUBLISH_DELETE
            self.public.save()
        super(Publishable, self).delete()

    def publish(self, dry_run=False, all_published=None):
        '''
        either publish changes or deletions, depending on
        whether this model is public or draft.
    
        public models will be examined to see if they need deleting
        and deleted if so.
        '''
        if self.is_public:
            self.publish_deletions(dry_run=dry_run, all_published=all_published)
        else:
            self.publish_changes(dry_run=dry_run, all_published=all_published)

    def _get_public_or_publish_changes(self, *arg, **kw):
        # only publish if we don't yet have an id for the
        # public model
        if self.public:
            return self.public
        return self.publish_changes(*arg, **kw)

    def publish_changes(self, dry_run=False, all_published=None, parent=None):
        '''
        publish changes to the model - basically copy all of it's content to another copy in the 
        database.
        if you set dry_run=True nothing will be written to the database.  combined with
        the all_published value one can therefore get information about what other models
        would be affected by this function
        '''

        assert not self.is_public, "Cannot publish public model - publish should be called from draft model"
        assert self.pk is not None, "Please save model before publishing"

        # avoid mutual recursion
        if all_published is None:
            all_published = NestedSet()

        if self in all_published:
            return self.public
        all_published.add(self, parent=parent)        

        public_version = self.public
        if not public_version:
            public_version = self.__class__(is_public=True)
        
        if self.publish_state == Publishable.PUBLISH_CHANGED:
            # copy over regular fields
            for field in self._meta.fields:
                if field.name in self.PublishMeta.excluded_fields():
                    continue
                
                value = getattr(self, field.name)
                if isinstance(field, RelatedField):
                    related = field.rel.to
                    if issubclass(related, Publishable):
                        if value is not None:
                            value = value._get_public_or_publish_changes(dry_run=dry_run, all_published=all_published, parent=self)
                
                if not dry_run:
                    setattr(public_version, field.name, value)
        
            # save the public version and update
            # state so we know everything is up-to-date
            if not dry_run:
                public_version.save()
                self.public = public_version
                self.publish_state = Publishable.PUBLISH_DEFAULT
                self.save(mark_changed=False)

        # copy over many-to-many fields
        for field in self._meta.many_to_many:
            name = field.name
            if name in self.PublishMeta.excluded_fields():
                continue
            
            m2m_manager = getattr(self, name)
            public_objs = list(m2m_manager.all())

            field_object, model, direct, m2m = self._meta.get_field_by_name(name)
            related = field_object.rel.to
            if issubclass(related, Publishable):
                public_objs = [p._get_public_or_publish_changes(dry_run=dry_run, all_published=all_published, parent=self) for p in public_objs]
            
            if not dry_run:
                public_m2m_manager = getattr(public_version, name)
                old_objs = public_m2m_manager.exclude(pk__in=[p.pk for p in public_objs])
                public_m2m_manager.remove(*old_objs)
                public_m2m_manager.add(*public_objs)

        # one-to-many reverse relations
        for obj in self._meta.get_all_related_objects():
            if issubclass(obj.model, Publishable):
                name = obj.get_accessor_name()
                if name in self.PublishMeta.excluded_fields():
                    continue
                if name not in self.PublishMeta.reverse_fields_to_publish():
                    continue
                if obj.field.rel.multiple:
                    related_items = getattr(self, name).all()
                    for related_item in related_items:
                        related_item.publish_changes(dry_run=dry_run, all_published=all_published, parent=self)

        return public_version
    
    def publish_deletions(self, all_published=None, parent=None, dry_run=False):
        '''
        actually delete models that have been marked for deletion
        '''
        assert self.is_public, "delete_if_marked should only be called from public model"
        
        if self.publish_state != Publishable.PUBLISH_DELETE:
            return  

        if all_published is None:
            all_published = NestedSet()

        if self in all_published:
            return
        
        all_published.add(self, parent=parent)

        for related in self._meta.get_all_related_objects():
            if not issubclass(related.model, Publishable):
                continue
            name = related.get_accessor_name()
            if name in self.PublishMeta.excluded_fields():
                continue
            try:
                instances = getattr(self, name).all()
            except AttributeError:
                instances = [getattr(self, name)]
            for instance in instances:
                instance.delete_if_marked(all_published=all_published, parent=self, dry_run=dry_run)
        
        if not dry_run:
            self.delete()


if getattr(settings, 'TESTING_PUBLISH', False):
    # classes to test that publishing etc work ok
    from django.utils.translation import ugettext_lazy as _    

    class Site(models.Model):
        title = models.CharField(max_length=100)
        domain = models.CharField(max_length=100)

    class FlatPage(Publishable):
        url = models.CharField(max_length=100, db_index=True)
        title = models.CharField(max_length=200)
        content = models.TextField(blank=True)
        enable_comments = models.BooleanField()
        template_name = models.CharField(max_length=70, blank=True)
        registration_required = models.BooleanField()
        sites = models.ManyToManyField(Site)

        class Meta:
            ordering = ['url']
    
    class Author(Publishable):
        name = models.CharField(max_length=100)
        profile = models.TextField(blank=True)

    class ChangeLog(models.Model):
        changed = models.DateTimeField(db_index=True, auto_now_add=True)
        message = models.CharField(max_length=200)

    class PageBlock(Publishable):
        page=models.ForeignKey('Page')
        content = models.TextField(blank=True)

    class Page(Publishable):
        slug = models.CharField(max_length=100, db_index=True)
        title = models.CharField(max_length=200)
        content = models.TextField(blank=True)
        
        parent = models.ForeignKey('self', blank=True, null=True)
        
        authors = models.ManyToManyField(Author)
        log = models.ManyToManyField(ChangeLog)        

        class Meta:
            ordering = ['slug']

        class PublishMeta(Publishable.PublishMeta):
            publish_exclude_fields = ['log']
            publish_reverse_fields = ['pageblock_set']

        def get_absolute_url(self):
            if not self.parent:
                return u'/%s/' % self.slug
            return '%s%s/' % (self.parent.get_absolute_url(), self.slug)


