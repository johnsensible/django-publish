from django.db import models
from django.conf import settings

# this takes some inspiration from the publisher stuff in
# django-cms 2.0
# e.g. http://github.com/digi604/django-cms-2.0/blob/master/publisher/models.py
#
# but we want this to be a reusable/standalone app and have a few different needs
#

class PublishableManager(models.Manager):
    
    def changed(self):
        '''all draft objects that have not been published yet'''
        return self.get_query_set().filter(is_public=False, publish_state=Publishable.PUBLISH_CHANGED)
    
    def draft(self):
        '''all draft objects'''
        return self.get_query_set().filter(is_public=False)
    
    def published(self):
        '''all public/published objects'''
        return self.get_query_set().filter(is_public=True)

class Publishable(models.Model):
    PUBLISH_DEFAULT = 0
    PUBLISH_CHANGED = 1
    PUBLISH_DELETE  = 2

    PUBLISH_CHOICES = ((PUBLISH_DEFAULT, 'Default'), (PUBLISH_CHANGED, 'Changed'), (PUBLISH_DELETE, 'Delete'))

    is_public = models.BooleanField(default=False, editable=False, db_index=True)
    publish_state = models.IntegerField(editable=False, db_index=True, choices=PUBLISH_CHOICES, default=PUBLISH_DEFAULT)
    public = models.OneToOneField('self', related_name='draft', null=True, editable=False)
    
    class Meta:
        abstract = True

    class PublishMeta:
        publish_exclude_fields = ['id', 'is_public', 'publish_state', 'public']

    objects = PublishableManager()

    def save(self, mark_changed=True, *arg, **kw):
        if not self.is_public and mark_changed:
            self.publish_state = Publishable.PUBLISH_CHANGED
        super(Publishable, self).save(*arg, **kw)

    def publish(self):
        if self.is_public:
            raise ValueError("Cannot publish public model - publish should be called from draft model")
        
        public_version = self.public
        if not public_version:
            public_version = self.__class__(is_public=True)
        
        # copy over regular fields
        for field in self._meta.fields:
            if field.name in self.PublishMeta.publish_exclude_fields:
                continue
            
            value = getattr(self, field.name)
            setattr(public_version, field.name, value)
        
        # save the public version and update
        # state so we know everything is up-to-date
        public_version.save()
        self.public = public_version
        self.publish_state = Publishable.PUBLISH_DEFAULT
        self.save(mark_changed=False)

        # copy over many-to-many fields
        for field in self._meta.many_to_many:
            name = field.name
            if name in self.PublishMeta.publish_exclude_fields:
                continue
            
            m2m_manager = getattr(self, name)
            public_m2m_manager = getattr(public_version, name)
            
            public_objs = list(m2m_manager.all())
            public_m2m_manager.exclude(pk__in=[p.pk for p in public_objs]).delete()
            public_m2m_manager.add(*public_objs)
            

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
