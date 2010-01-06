from django.conf.urls.defaults import *
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    ('^admin/', include(admin.site.urls)),

    ('^', include('pubcms.urls')),
)
