from django.utils.encoding import smart_unicode

from models import Publishable

try:
    # only using this code if on before Django 1.4
    from django.contrib.admin.filterspecs import FilterSpec, RelatedFilterSpec
    
    
    class PublishableRelatedFilterSpec(RelatedFilterSpec):
        def __init__(self, f, request, params, model, model_admin):
            super(PublishableRelatedFilterSpec, self).__init__(f, request, params, model, model_admin)
            # to keep things simple we'll just remove all "non-draft" instance from list
            rel_model = f.rel.to
            queryset = rel_model._default_manager.complex_filter(f.rel.limit_choices_to).draft_and_deleted()
            if hasattr(f.rel, 'get_related_field'):
                lst = [(getattr(x, f.rel.get_related_field().attname), smart_unicode(x)) for x in queryset]
            else:
                lst = [(x._get_pk_val(), smart_unicode(x)) for x in queryset]
            self.lookup_choices = lst
    
    
    def is_publishable_spec(f):
        return bool(f.rel) and issubclass(f.rel.to, Publishable)
    
    
    def register_filter_spec(test, factory):
        # NB this may need updating for Django 1.2,
        # but basically we want this to get run before
        # RelatedFilterSpec - 1.2 should have a method to do this
        FilterSpec.filter_specs.insert(0, (test, factory))
    
    
    register_filter_spec(is_publishable_spec, PublishableRelatedFilterSpec)
except ImportError:
    pass

