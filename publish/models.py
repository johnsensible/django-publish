from django.db import models
from django.db.models.query import QuerySet, Q
from django.db.models.base import ModelBase
from django.db.models.fields.related import RelatedField
from django.conf import settings

from utils import NestedSet
from signals import pre_publish, post_publish

# this takes some inspiration from the publisher stuff in
# django-cms 2.0
# e.g. http://github.com/digi604/django-cms-2.0/blob/master/publisher/models.py
#
# but we want this to be a reusable/standalone app and have a few different needs
#

class PublishException(Exception):
    pass

class PublishableQuerySet(QuerySet):

    def changed(self):
        '''all draft objects that have not been published yet'''
        return self.filter(Publishable.Q_CHANGED)
    
    def deleted(self):
        '''public objects that need deleting'''
        return self.filter(Publishable.Q_DELETED)

    def draft(self):
        '''all draft objects'''
        return self.filter(Publishable.Q_DRAFT)
   
    def draft_and_deleted(self):
        return self.filter(Publishable.Q_DRAFT | Publishable.Q_DELETED)
 
    def published(self):
        '''all public/published objects'''
        return self.filter(Publishable.Q_PUBLISHED)

    def publish(self, all_published=None):
        '''publish all models in this queryset'''
        if all_published is None:
            all_published = NestedSet()
        for p in self:
            p.publish(all_published=all_published)

    def delete(self, mark_for_deletion=True):
        '''
        override delete so that we call delete on each object separately, as delete needs
        to set some flags etc
        '''
        for p in self:
            p.delete(mark_for_deletion=mark_for_deletion)


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


class PublishableBase(ModelBase):
    
    def __new__(cls, name, bases, attrs):
        new_class = super(PublishableBase, cls).__new__(cls, name, bases, attrs)
        # insert an extra permission in for "Can publish"
        # as well as a "method" to find name of publish_permission for this object
        opts = new_class._meta
        name = u'Can publish %s' % opts.verbose_name
        code = u'publish_%s' % opts.object_name.lower()
        opts.permissions = tuple(opts.permissions) + ((code, name), )
        opts.get_publish_permission = lambda: code
        
        return new_class
    

class Publishable(models.Model):
    __metaclass__ = PublishableBase

    PUBLISH_DEFAULT = 0
    PUBLISH_CHANGED = 1
    PUBLISH_DELETE  = 2

    PUBLISH_CHOICES = ((PUBLISH_DEFAULT, 'Published'), (PUBLISH_CHANGED, 'Changed'), (PUBLISH_DELETE, 'To be deleted'))

    # make these available here so can easily re-use them in other code
    Q_PUBLISHED = Q(is_public=True)
    Q_DRAFT     = Q(is_public=False) & ~Q(publish_state=PUBLISH_DELETE)
    Q_CHANGED   = Q(is_public=False, publish_state=PUBLISH_CHANGED)
    Q_DELETED   = Q(is_public=False, publish_state=PUBLISH_DELETE)

    is_public = models.BooleanField(default=False, editable=False, db_index=True)
    publish_state = models.IntegerField('Publication status', editable=False, db_index=True, choices=PUBLISH_CHOICES, default=PUBLISH_DEFAULT)
    public = models.OneToOneField('self', related_name='draft', null=True, editable=False)
    
    class Meta:
        abstract = True

    class PublishMeta(object):
        publish_exclude_fields = ['id', 'is_public', 'publish_state', 'public', 'draft']
        publish_reverse_fields = []
        publish_functions = {}        

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

        @classmethod
        def find_publish_function(cls, field_name, default_function):
            '''
                Search to see if there is a function to copy the given field over.
                Function should take same params as setattr()
            '''
            for clazz in cls.__mro__:
                publish_functions = getattr(clazz, 'publish_functions', {})
                fn = publish_functions.get(field_name, None)
                if fn:
                    return fn
            return default_function

    objects = PublishableManager()
    
    def is_marked_for_deletion(self):
        return self.publish_state == Publishable.PUBLISH_DELETE

    def get_public_absolute_url(self):
        if self.public:
            return self.public.get_absolute_url()
        # effectively this method doesn't exist until we
        # have a public instance
        raise AttributeError("get_public_absolute_url")

    def save(self, mark_changed=True, *arg, **kw):
        if not self.is_public and mark_changed:
            if self.publish_state == Publishable.PUBLISH_DELETE:
                raise PublishException("Attempting to save model marked for deletion")
            self.publish_state = Publishable.PUBLISH_CHANGED

        super(Publishable, self).save(*arg, **kw)
    
    def delete(self, mark_for_deletion=True):
        if self.public and mark_for_deletion:
            self.publish_state = Publishable.PUBLISH_DELETE
            self.save(mark_changed=False)
        else:
            super(Publishable, self).delete()

    def undelete(self):
        self.publish_state = Publishable.PUBLISH_CHANGED
        self.save(mark_changed=False)

    def _pre_publish(self, dry_run, all_published, deleted=False):
        if not dry_run:
            sender = self.__class__
            pre_publish.send(sender=sender, instance=self, deleted=deleted)

    def _post_publish(self, dry_run, all_published, deleted=False):
        if not dry_run:
            # we need to make sure we get the instance that actually
            # got published (in case it was indirectly published elsewhere)
            sender = self.__class__
            instance = all_published.original(self)
            post_publish.send(sender=sender, instance=instance, deleted=deleted)


    def publish(self, dry_run=False, all_published=None, parent=None):
        '''
        either publish changes or deletions, depending on
        whether this model is public or draft.
    
        public models will be examined to see if they need deleting
        and deleted if so.
        '''
        if self.is_public:
            raise PublishException("Cannot publish public model - publish should be called from draft model")
        if self.pk is None:
            raise PublishException("Please save model before publishing")
         
        if self.publish_state == Publishable.PUBLISH_DELETE:
            self.publish_deletions(dry_run=dry_run, all_published=all_published, parent=parent)
            return None
        else:
            return self.publish_changes(dry_run=dry_run, all_published=all_published, parent=parent)
        
    def _get_public_or_publish(self, *arg, **kw):
        # only publish if we don't yet have an id for the
        # public model
        if self.public:
            return self.public
        return self.publish(*arg, **kw)

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
            return all_published.original(self).public

        all_published.add(self, parent=parent)        

        self._pre_publish(dry_run, all_published)

        public_version = self.public
        if not public_version:
            public_version = self.__class__(is_public=True)
        
        excluded_fields = self.PublishMeta.excluded_fields()
        reverse_fields_to_publish = self.PublishMeta.reverse_fields_to_publish()
        
        if self.publish_state == Publishable.PUBLISH_CHANGED:
            # copy over regular fields
            for field in self._meta.fields:
                if field.name in excluded_fields:
                    continue
                
                value = getattr(self, field.name)
                if isinstance(field, RelatedField):
                    related = field.rel.to
                    if issubclass(related, Publishable):
                        if value is not None:
                            value = value._get_public_or_publish(dry_run=dry_run, all_published=all_published, parent=self)
                
                if not dry_run:
                    publish_function = self.PublishMeta.find_publish_function(field.name, setattr)
                    publish_function(public_version, field.name, value)
        
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
            if name in excluded_fields:
                continue
            
            m2m_manager = getattr(self, name)
            public_objs = list(m2m_manager.all())

            field_object, model, direct, m2m = self._meta.get_field_by_name(name)
            if field_object.rel.through:
                # see if we can work out which reverse relationship this is
                related_model = field_object.rel.through_model
                # this will be db name (e.g. with _id on end)
                m2m_reverse_name = field_object.m2m_reverse_name()
                for reverse_field in related_model._meta.fields:
                    if reverse_field.column == m2m_reverse_name:
                        related_name = reverse_field.name
                        related_field = getattr(related_model, related_name).field
                        reverse_name = related_field.related.get_accessor_name()
                        reverse_fields_to_publish.append(reverse_name)
                        break
                continue # m2m via through table won't be dealt with here
                        
            related = field_object.rel.to
            if issubclass(related, Publishable):
                public_objs = [p._get_public_or_publish(dry_run=dry_run, all_published=all_published, parent=self) for p in public_objs]
            
            if not dry_run:
                public_m2m_manager = getattr(public_version, name)
                old_objs = public_m2m_manager.exclude(pk__in=[p.pk for p in public_objs])
                public_m2m_manager.remove(*old_objs)
                public_m2m_manager.add(*public_objs)

        # one-to-many reverse relations
        for obj in self._meta.get_all_related_objects():
            if issubclass(obj.model, Publishable):
                name = obj.get_accessor_name()
                if name in excluded_fields:
                    continue
                if name not in reverse_fields_to_publish:
                    continue
                if obj.field.rel.multiple:
                    related_items = getattr(self, name).all()
                    for related_item in related_items:
                        related_item.publish(dry_run=dry_run, all_published=all_published, parent=self)
                    
                    # make sure we tidy up anything that needs deleting
                    if self.public and not dry_run:
                        public_ids = related_items.values('public_id')
                        deleted_items = getattr(self.public, name).exclude(pk__in=public_ids)
                        deleted_items.delete(mark_for_deletion=False)
                    #    for deleted_item in deleted_items:
                    #        deleted_item.publish_deletions(dry_run=dry_run, all_published=all_published, parent=self)
        
        self._post_publish(dry_run, all_published)

        return public_version
    
    def publish_deletions(self, all_published=None, parent=None, dry_run=False):
        '''
        actually delete models that have been marked for deletion
        '''
        if self.publish_state != Publishable.PUBLISH_DELETE:
            return  

        if all_published is None:
            all_published = NestedSet()

        if self in all_published:
            return
        
        all_published.add(self, parent=parent)

        self._pre_publish(dry_run, all_published, deleted=True)

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
                instance.publish_deletions(all_published=all_published, parent=self, dry_run=dry_run)
        
        if not dry_run:
            public = self.public
            self.delete(mark_for_deletion=False)
            if public:
                public.delete(mark_for_deletion=False)

        self._post_publish(dry_run, all_published, deleted=True)


if getattr(settings, 'TESTING_PUBLISH', False):
    # classes to test that publishing etc work ok
    from django.utils.translation import ugettext_lazy as _
    from datetime import datetime

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
        
        def get_absolute_url(self):
            if self.is_public:
                return self.url
            return '%s*' % self.url
    
    class Author(Publishable):
        name = models.CharField(max_length=100)
        profile = models.TextField(blank=True)

    class ChangeLog(models.Model):
        changed = models.DateTimeField(db_index=True, auto_now_add=True)
        message = models.CharField(max_length=200)
    
    class Tag(models.Model):
        title = models.CharField(max_length=100, unique=True)
        slug = models.CharField(max_length=100)
   
    # publishable model with a reverse relation to 
    # page (as a child) 
    class PageBlock(Publishable):
        page=models.ForeignKey('Page')
        content = models.TextField(blank=True)
    
    # non-publishable reverse relation to page (as a child)
    class Comment(models.Model):
        page=models.ForeignKey('Page')
        comment = models.TextField()
    
    def update_pub_date(page, field_name, value):
        # ignore value entirely and replace with now
        setattr(page, field_name, update_pub_date.pub_date)
    update_pub_date.pub_date = datetime.now()

    class Page(Publishable):
        slug = models.CharField(max_length=100, db_index=True)
        title = models.CharField(max_length=200)
        content = models.TextField(blank=True)
        pub_date = models.DateTimeField(default=datetime.now)        
 
        parent = models.ForeignKey('self', blank=True, null=True)
        
        authors = models.ManyToManyField(Author, blank=True)
        log = models.ManyToManyField(ChangeLog, blank=True)
        tags = models.ManyToManyField(Tag, through='PageTagOrder', blank=True)

        class Meta:
            ordering = ['slug']

        class PublishMeta(Publishable.PublishMeta):
            publish_exclude_fields = ['log']
            publish_reverse_fields = ['pageblock_set']
            publish_functions = { 'pub_date': update_pub_date }

        def get_absolute_url(self):
            if not self.parent:
                return u'/%s/' % self.slug
            return '%s%s/' % (self.parent.get_absolute_url(), self.slug)
    
    class PageTagOrder(Publishable):
        # note these are named in non-standard way to
        # ensure we are getting correct names
        tagged_page=models.ForeignKey(Page)
        page_tag=models.ForeignKey(Tag)
        tag_order=models.IntegerField()


