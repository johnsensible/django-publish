from django.conf import settings
 
if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase
    from django.contrib.admin.sites import AdminSite
    from django.forms.models import ModelChoiceField, ModelMultipleChoiceField
    from publish.models import Publishable, FlatPage, Site, Page, Author
    from publish.admin import PublishableAdmin

    class TestBasicPublishable(TransactionTestCase):
        
        def setUp(self):
            super(TestBasicPublishable, self).setUp()
            self.flat_page = FlatPage(url='/my-page', title='my page',
                                      content='here is some content', 
                                      enable_comments=False,
                                      registration_required=True)


        def test_save_marks_changed(self):
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save(mark_changed=False)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
        
        def test_publish_excludes_fields(self):
            self.flat_page.save()
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failIfEqual(self.flat_page.id, self.flat_page.public.id)
            self.failUnless(self.flat_page.public.is_public)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.public.publish_state)

        def test_publish_check_is_not_public(self):
            try:
                self.flat_page.is_public = True
                self.flat_page.publish()
                self.fail("Should not be able to publish public models")
            except AssertionError:
                pass

        def test_publish_check_has_id(self):
            try:
                self.flat_page.publish()
                self.fail("Should not be able to publish unsaved models")
            except AssertionError:
                pass
        
        def test_publish_simple_fields(self):
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
            self.failIf(self.flat_page.public) # should not be a public version yet
            
            self.flat_page.publish()
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.failUnless(self.flat_page.public)
            
            for field in 'url', 'title', 'content', 'enable_comments', 'registration_required': 
                self.failUnlessEqual(getattr(self.flat_page, field), getattr(self.flat_page.public, field))
        
        def test_published_simple_field_repeated(self):
            self.flat_page.save()
            self.flat_page.publish()
            
            public = self.flat_page.public
            self.failUnless(public)
            
            self.flat_page.title = 'New Title'
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

            self.failUnlessEqual(public, self.flat_page.public)
            self.failIfEqual(public.title, self.flat_page.title)

            self.flat_page.publish()
            self.failUnlessEqual(public, self.flat_page.public)
            self.failUnlessEqual(public.title, self.flat_page.title)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)

        def test_delete_after_publish(self):
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public
            self.failUnless(public)
            
            self.flat_page.delete()
            self.failUnlessEqual(Publishable.PUBLISH_DELETE, public.publish_state)

            self.failUnlessEqual([public], list(FlatPage.objects.all()))

        def test_delete_before_publish(self):
            self.flat_page.save()
            self.flat_page.delete()
            self.failUnlessEqual([], list(FlatPage.objects.all()))
 

    class TestPublishableManager(TransactionTestCase):
        
        def setUp(self):
            super(TransactionTestCase, self).setUp()
            self.flat_page1 = FlatPage.objects.create(url='/url1/', title='title 1')
            self.flat_page2 = FlatPage.objects.create(url='/url2/', title='title 2')
        
        def test_all(self): 
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.all()))
            
            # publishing will produce extra copies
            self.flat_page1.publish()
            self.failUnlessEqual(3, FlatPage.objects.count())
            
            self.flat_page2.publish()
            self.failUnlessEqual(4, FlatPage.objects.count())


        def test_changed(self):
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.changed()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page2], list(FlatPage.objects.changed()))
            
            self.flat_page2.publish()
            self.failUnlessEqual([], list(FlatPage.objects.changed()))
        
        def test_draft(self):
            # draft should stay the same pretty much always
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))
            
            self.flat_page2.publish()
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))
        
        def test_published(self):
            self.failUnlessEqual([], list(FlatPage.objects.published()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page1.public], list(FlatPage.objects.published()))
            
            self.flat_page2.publish()
            self.failUnlessEqual([self.flat_page1.public, self.flat_page2.public], list(FlatPage.objects.published()))

        def test_deleted(self):
            self.failUnlessEqual([], list(FlatPage.objects.deleted()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([], list(FlatPage.objects.deleted()))

            public = self.flat_page1.public
            self.flat_page1.delete()
            self.failUnlessEqual([public], list(FlatPage.objects.deleted()))

        def test_delete_marked(self):
            self.flat_page1.publish()

            public = self.flat_page1.public
            self.flat_page1.delete()
            
            self.failUnless(public in FlatPage.objects.published())
            self.failUnlessEqual([public], list(FlatPage.objects.deleted()))            

            public._delete_marked()
            self.failIf(public in FlatPage.objects.published())

    class TestPublishableManyToMany(TransactionTestCase):
        
        def setUp(self):
            super(TestPublishableManyToMany, self).setUp()
            self.flat_page = FlatPage.objects.create(
                                      url='/my-page', title='my page',
                                      content='here is some content', 
                                      enable_comments=False,
                                      registration_required=True)
            self.site1 = Site.objects.create(title='my site', domain='mysite.com')
            self.site2 = Site.objects.create(title='a site', domain='asite.com')
        
        def test_publish_no_sites(self):
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))
        
        def test_publish_add_site(self):
            self.flat_page.sites.add(self.site1)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))
        
        def test_publish_repeated_add_site(self):
            self.flat_page.sites.add(self.site1)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))
            
            self.flat_page.sites.add(self.site2)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))

            self.flat_page.publish()
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))
        
        def test_publish_remove_site(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.sites.remove(self.site1)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.publish()
            self.failUnlessEqual([self.site2], list(self.flat_page.public.sites.all()))

        def test_publish_clear_sites(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.sites.clear()
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.publish()
            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))

        def test_publish_sites_cleared_not_deleted(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.flat_page.sites.clear()
            self.flat_page.publish()

            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))
            
            self.failIfEqual([], list(Site.objects.all()))

            


    class TestPublishableRecursiveForeignKey(TransactionTestCase):

        def setUp(self):
            super(TestPublishableRecursiveForeignKey, self).setUp()
            self.page1 = Page.objects.create(slug='page1', title='page 1', content='some content')
            self.page2 = Page.objects.create(slug='page2', title='page 2', content='other content', parent=self.page1)
        
        def test_publish_parent(self):
            # this shouldn't publish the child page
            self.page1.publish()
            self.failUnless(self.page1.public)
            self.failIf(self.page1.public.parent)
            
            page2 = Page.objects.get(id=self.page2.id)
            self.failIf(page2.public)
        
        def test_publish_child_parent_already_published(self):
            self.page1.publish()
            self.page2.publish()

            self.failUnless(self.page1.public)
            self.failUnless(self.page2.public)

            self.failIf(self.page1.public.parent)
            self.failUnless(self.page2.public.parent)

            self.failIfEqual(self.page1, self.page2.public.parent)

            self.failUnlessEqual('/page1/', self.page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', self.page2.public.get_absolute_url())

        def test_publish_child_parent_not_already_published(self):
            self.page2.publish()
            
            page1 = Page.objects.get(id=self.page1.id)
            self.failUnless(page1.public)
            self.failUnless(self.page2.public)

            self.failIf(page1.public.parent)
            self.failUnless(self.page2.public.parent)

            self.failIfEqual(page1, self.page2.public.parent)

            self.failUnlessEqual('/page1/', self.page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', self.page2.public.get_absolute_url())

        def test_publish_repeated(self):
            self.page1.publish()
            self.page2.publish()
            
            self.page1.slug='main'
            self.page1.save()

            self.failUnlessEqual('/main/', self.page1.get_absolute_url())
            
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            self.failUnlessEqual('/page1/', page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', page2.public.get_absolute_url())
            
            page1.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            self.failUnlessEqual('/main/', page1.public.get_absolute_url())
            self.failUnlessEqual('/main/page2/', page2.public.get_absolute_url())
            
            page1.slug='elsewhere'
            page1.save()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            page2.slug='meanwhile'
            page2.save()
            page2.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            
            # only page2 should be published, not page1, as page1 already published
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page2.publish_state)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, page1.publish_state)

            self.failUnlessEqual('/main/', page1.public.get_absolute_url())
            self.failUnlessEqual('/main/meanwhile/', page2.public.get_absolute_url())

            page1.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)

            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page2.publish_state)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page1.publish_state)

            self.failUnlessEqual('/elsewhere/', page1.public.get_absolute_url())
            self.failUnlessEqual('/elsewhere/meanwhile/', page2.public.get_absolute_url())

        def test_delete_marked(self):
            self.page1.publish()
            self.page2.publish()
            
            public = self.page2.public
            self.page2.delete()
            self.failUnlessEqual([public], list(Page.objects.deleted()))

            public._delete_marked()
            self.failUnlessEqual([self.page1.public], list(Page.objects.published()))
            self.failUnlessEqual([], list(Page.objects.deleted()))

    class TestPublishableRecursiveManyToManyField(TransactionTestCase):

        def setUp(self):
            super(TestPublishableRecursiveManyToManyField, self).setUp()
            self.page = Page.objects.create(slug='page1', title='page 1', content='some content')
            self.author1 = Author.objects.create(name='author1', profile='a profile')
            self.author2 = Author.objects.create(name='author2', profile='something else')

        def test_publish_add_author(self):
            self.page.authors.add(self.author1)
            self.page.publish()
            self.failUnless(self.page.public)

            author1 = Author.objects.get(id=self.author1.id)
            self.failUnless(author1.public)
            self.failIfEqual(author1.id, author1.public.id)
            self.failUnlessEqual(author1.name, author1.public.name)
            self.failUnlessEqual(author1.profile, author1.public.profile)            

            self.failUnlessEqual([author1.public], list(self.page.public.authors.all()))

        def test_publish_repeated_add_author(self):
            self.page.authors.add(self.author1)
            self.page.publish()
            
            self.failUnless(self.page.public)

            self.page.authors.add(self.author2)
            author1 = Author.objects.get(id=self.author1.id)
            self.failUnlessEqual([author1.public], list(self.page.public.authors.all()))

            self.page.publish()
            author1 = Author.objects.get(id=self.author1.id)
            author2 = Author.objects.get(id=self.author2.id)
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

        def test_publish_clear_authors(self):
            self.page.authors.add(self.author1, self.author2)
            self.page.publish()

            author1 = Author.objects.get(id=self.author1.id)
            author2 = Author.objects.get(id=self.author2.id)
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

            self.page.authors.clear()
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

            self.page.publish()
            self.failUnlessEqual([], list(self.page.public.authors.all()))

    class TestInfiniteRecursion(TransactionTestCase):
        
        def setUp(self):
            super(TestInfiniteRecursion, self).setUp()
            
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2', parent=self.page1)
            self.page1.parent = self.page2
            self.page1.save()
        
        def test_publish_recursion_breaks(self):
            self.page1.publish() # this should simple run without an error

    class TestPublishableAdmin(TransactionTestCase):
        
        def setUp(self):
            super(TestPublishableAdmin, self).setUp()
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2')
            self.page1.publish()
            self.page2.publish()

            self.author1 = Author.objects.create(name='a1')
            self.author2 = Author.objects.create(name='a2')
            self.author1.publish()
            self.author2.publish()

            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(Page, self.admin_site)

        def test_queryset(self):
            # make sure we only get back draft objects
            request = None
            
            self.failUnlessEqual(
                set([self.page1, self.page1.public, self.page2, self.page2.public]),
                set(Page.objects.all())
            )
            self.failUnlessEqual(
                set([self.page1, self.page2]),
                set(self.page_admin.queryset(request))
            )

        def test_formfield_for_foreignkey(self):
            # foreign key forms fields in admin
            # for publishable models should be filtered
            # to hide public object

            request = None
            parent_field = None
            for field in Page._meta.fields:
                if field.name == 'parent':
                    parent_field = field
                    break
            self.failUnless(parent_field)
            
            choice_field = self.page_admin.formfield_for_foreignkey(parent_field, request)
            self.failUnless(choice_field)
            self.failUnless(isinstance(choice_field, ModelChoiceField))

            self.failUnlessEqual(
                set([self.page1, self.page1.public, self.page2, self.page2.public]),
                set(Page.objects.all())
            )
            self.failUnlessEqual(
                set([self.page1, self.page2]),
                set(choice_field.queryset)
            )

        def test_formfield_for_manytomany(self):
            request = None
            authors_field = None
            for field in Page._meta.many_to_many:
                if field.name == 'authors':
                    authors_field = field
                    break
            self.failUnless(authors_field)

            choice_field = self.page_admin.formfield_for_manytomany(authors_field, request)
            self.failUnless(choice_field)
            self.failUnless(isinstance(choice_field, ModelMultipleChoiceField))

            self.failUnlessEqual(
                set([self.author1, self.author1.public, self.author2, self.author2.public]),
                set(Author.objects.all())
            )
            self.failUnlessEqual(
                set([self.author1, self.author2]),
                set(choice_field.queryset)
            )

