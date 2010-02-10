import django.dispatch

# instance is the instance being published, deleted is a boolean to indicate whether the instance
# was being deleted (rather than changed)
pre_publish  = django.dispatch.Signal(providing_args=['instance', 'deleted'])
post_publish = django.dispatch.Signal(providing_args=['instance', 'deleted'])
