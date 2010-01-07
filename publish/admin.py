from django.contrib import admin

from models import Publishable
from actions import publish_selected

class PublishableAdmin(admin.ModelAdmin):
    
    actions = [publish_selected]
    publish_confirmation_template = None

    def queryset(self, request):
        # only show draft models in admin
        qs = super(PublishableAdmin, self).queryset(request)
        return qs.draft()

    def _draft_queryset(self, db_field, kwargs):
        # see if we need to filter the field's queryset
        model = db_field.rel.to
        if issubclass(model, Publishable):
            kwargs['queryset'] = model._default_manager.draft()

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        self._draft_queryset(db_field, kwargs)
        return super(PublishableAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
    
    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        self._draft_queryset(db_field, kwargs)
        return super(PublishableAdmin, self).formfield_for_manytomany(db_field, request, **kwargs)

