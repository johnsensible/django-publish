import django.dispatch

pre_publish  = django.dispatch.Signal(providing_args=['instance'])
post_publish = django.dispatch.Signal(providing_args=['instance'])
