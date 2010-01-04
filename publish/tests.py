from django.conf import settings
 
if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase
    from publish.models import Publishable, FlatPage

    class TestBasicPublishable(TransactionTestCase):
        
        def setUp(self):
            super(TestBasicPublishable, self).setUp()
            self.flat_page = FlatPage()
            self.flat_page.url = '/my-page/'
            self.flat_page.title = 'my page'
            self.flat_page.content = 'here is some content'
            self.flat_page.enable_comments = False
            self.flat_page.registration_required = True


        def test_save_marks_changed(self):
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save(mark_changed=False)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
        
        def test_publish_check_is_not_public(self):
            try:
                self.flat_page.is_public = True
                self.flat_page.publish()
                self.fail("Should not be able to publish public models")
            except ValueError:
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

