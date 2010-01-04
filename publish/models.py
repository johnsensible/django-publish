from django.db import models
from django.conf import settings

# this takes some inspiration from the publisher stuff in
# django-cms 2.0
# e.g. http://github.com/digi604/django-cms-2.0/blob/master/publisher/models.py
#
# but we want this to be a reusable/standalone app and have a few different needs
#

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

    def save(self, mark_changed=True, *arg, **kw):
        if not self.is_public and mark_changed:
            self.publish_state = Publishable.PUBLISH_CHANGED
        super(Publishable, self).save(*arg, **kw)

    def publish(self):
        pass

if getattr(settings, 'TESTING_PUBLISH', False):
    # classes to test that publishing etc work ok
    from django.contrib.sites.models import Site
    from django.utils.translation import ugettext_lazy as _    

    class FlatPage(Publishable):
        url = models.CharField(_('URL'), max_length=100, db_index=True)
        title = models.CharField(_('title'), max_length=200)
        content = models.TextField(_('content'), blank=True)
        enable_comments = models.BooleanField(_('enable comments'))
        template_name = models.CharField(_('template name'), max_length=70, blank=True,
        help_text=_("Example: 'flatpages/contact_page.html'. If this isn't provided, the system will use 'flatpages/default.html'."))
        registration_required = models.BooleanField(_('registration required'), help_text=_("If this is checked, only logged-in users will be able to view the page."))
        sites = models.ManyToManyField(Site)
