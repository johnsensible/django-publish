from django.contrib import admin

from publish.admin import PublishableAdmin
from pubcms.models import Page, Category

class PageAdmin(PublishableAdmin):
    prepopulated_fields = {"slug": ("title",)}

class CategoryAdmin(PublishableAdmin):
    prepopulated_fields = {"slug": ("name",)}

admin.site.register(Page, PageAdmin)
admin.site.register(Category, CategoryAdmin)

