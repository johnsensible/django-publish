from django.contrib import admin

from publish.admin import PublishableAdmin, PublishableStackedInline
from pubcms.models import Page, PageBlock, Category, Image

class PageBlockInlineAdmin(PublishableStackedInline):
    model = PageBlock
    extra = 1

class PageAdmin(PublishableAdmin):
    inlines = [PageBlockInlineAdmin]
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ['publish_state', 'categories']

class CategoryAdmin(PublishableAdmin):
    prepopulated_fields = {"slug": ("name",)}

admin.site.register(Page, PageAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Image, PublishableAdmin)

