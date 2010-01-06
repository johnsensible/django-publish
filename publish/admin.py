from django.contrib import admin

from models import Publishable

class PublishableAdmin(admin.ModelAdmin):
    
    def queryset(self, request):
        # only show draft models in admin
        qs = super(PublishableAdmin, self).queryset(request)
        return qs.draft()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        print "formfield_for_foreignkey"
        model = db_field.rel.to
        if issubclass(model, Publishable):
            kwargs['queryset'] = model._default_manager.draft()
        return super(PublishableAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
