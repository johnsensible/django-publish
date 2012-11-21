from django.utils.encoding import smart_unicode

from .models import Publishable


try:
    from django.contrib.admin.filters import FieldListFilter, RelatedFieldListFilter
except ImportError:
    # only using this code if on before Django 1.4
    from django.contrib.admin.filterspecs import FilterSpec, RelatedFilterSpec as RelatedFieldListFilter
    
    class FieldListFilter(object):
        @classmethod
        def register(cls, test, list_filter_class, take_priority=False):
            if take_priority:
                FilterSpec.filter_specs.insert(0, (test, list_filter_class))
            else:
                FilterSpec.filter_specs.append((test, list_filter_class))


def is_publishable_filter(f):
    return bool(f.rel) and issubclass(f.rel.to, Publishable)


class PublishableRelatedFieldListFilter(RelatedFieldListFilter):
    def __init__(self, field, request, params, model, model_admin, *arg, **kw):
        super(PublishableRelatedFieldListFilter, self).__init__(field, request, params, model, model_admin, *arg, **kw)
        # to keep things simple we'll just remove all "non-draft" instance from list
        rel_model = field.rel.to
        queryset = rel_model._default_manager.complex_filter(field.rel.limit_choices_to).draft_and_deleted()
        if hasattr(field.rel, 'get_related_field'):
            lst = [(getattr(x, field.rel.get_related_field().attname), smart_unicode(x)) for x in queryset]
        else:
            lst = [(x._get_pk_val(), smart_unicode(x)) for x in queryset]
        self.lookup_choices = lst


FieldListFilter.register(is_publishable_filter, PublishableRelatedFieldListFilter, take_priority=True)

