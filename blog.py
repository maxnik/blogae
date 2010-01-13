from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import os
from google.appengine.ext.webapp import template

from google.appengine.ext import db

from google.appengine.api import users

import re

import urllib

import math

template.register_template_library('templatetags')

def slugify(str):
    without_punctuation = re.sub(r'[^a-z0-9-\s]', '', str.lower())
    without_spaces = re.sub(r'\s+', '-', without_punctuation.strip())
    return without_spaces

class Post(db.Model):
    title = db.StringProperty(required = True)
    body = db.TextProperty(required = True)
    tags = db.StringListProperty()
    created = db.DateTimeProperty(auto_now_add = True)

    def absolute_url(self):
        return "/posts/%d-%s" % (self.key().id(), slugify(self.title))

    def edit_url(self):
        return "/posts/edit/%d" % self.key().id()

    def quoted_title(self):
        return urllib.quote_plus(self.title)

class Tag(db.Model):
    title = db.StringProperty(required = True)
    posts_count = db.IntegerProperty()

    def absolute_url(self):
        return "/tags/%d-%s" % (self.key().id(), slugify(self.title))

BLOG_TITLE = 'Title of Blog'

POSTS_PER_PAGE = 5

class AbstractRequestHandler(webapp.RequestHandler):

    def initialize(self, *args):
        webapp.RequestHandler.initialize(self, *args)
        self.template_values = {'title': BLOG_TITLE,
                                'blog_title': BLOG_TITLE,
                                'host': self.request.headers.get('host')}        
        self.template_values['tags'] = Tag.all().order('-posts_count').order('title')

        if users.is_current_user_admin():
            self.template_values['is_admin'] = True
            self.template_values['logout_url'] = users.create_logout_url('/')

    def render_template(self, template_name, template_vars = {}):
        template_path = os.path.join(os.path.dirname(__file__), 'templates', template_name)
        self.template_values.update(template_vars)
        self.response.out.write(template.render(template_path, self.template_values))

class MainPage(AbstractRequestHandler):

    def get(self):
        total_pages = int(math.ceil(Post.all().count() / float(POSTS_PER_PAGE)))
        page = self.request.get_range('page', min_value = 1, max_value = total_pages, default = 1)
        posts = Post.all().order('-created').fetch(POSTS_PER_PAGE, (page - 1) * POSTS_PER_PAGE)
        self.render_template('posts.html', {'posts': posts,
                                            'path': self.request.path,
                                            'page': page,
                                            'total_pages': total_pages,
                                            'title': 'Fresh posts about something'})
    
class NewPostHandler(AbstractRequestHandler):

    def get(self):
        template_values = {'title': 'Create new blog post',
                           'post_title': '',
                           'post_body': '',
                           'post_tags': ''}
        self.render_template('post_form.html', template_values)

    def post(self):
        post_params = {'post_title': self.request.get('post_title'),
                       'post_body': self.request.get('post_body'),
                       'post_tags': self.request.get('post_tags')}
        tags = post_params['post_tags'].split(',')
        tags = [tag.strip() for tag in tags]
        tags.sort()
        try:
            blogpost = Post(title = post_params['post_title'],
                            body = post_params['post_body'],
                            tags = tags)
            blogpost.put()
        except db.BadValueError:
            self.render_template('post_form.html', post_params)
        else:
            self.redirect('/')

class ShowPostHandler(AbstractRequestHandler):

    def get(self, post_id):
        try:
            blogpost = Post.get_by_id(int(post_id))
            if blogpost:
                self.render_template('post.html', {'post': blogpost,
                                                   'title': blogpost.title,
                                                   'url': self.request.url})
            else:
                raise db.BadKeyError()
        except db.BadKeyError:
            self.error(404)
            self.render_template('page_not_found.html')

class EditPostHandler(AbstractRequestHandler):

    def get(self, post_id):
        blogpost = Post.get_by_id(int(post_id))
        template_values = {'post_title': blogpost.title,
                           'post_body': blogpost.body,
                           'post_tags': ','.join(blogpost.tags).strip(),
                           'title': 'Edit blog post'}
        self.render_template('post_form.html', template_values)

    def post(self, post_id):
        post_params = {'post_title': self.request.get('post_title'),
                       'post_body': self.request.get('post_body'),
                       'post_tags': self.request.get('post_tags')}
        tags = post_params['post_tags'].split(',')
        tags = [tag.strip() for tag in tags]
        tags.sort()
        blogpost = Post.get_by_id(int(post_id))
        blogpost.title = post_params['post_title']
        blogpost.body = post_params['post_body']
        blogpost.tags = tags            
        try:
            blogpost.put()
        except db.BadValueError:
            self.render_template('post_form.html', post_params)
        else:
            self.redirect(blogpost.absolute_url())

class UpdateTagsHandler(webapp.RequestHandler):

    def get(self):
        posts = Post.all()
        tags = Tag.all()

        tag_titles = {}
        for post in posts:
            for tag_title in post.tags:
                posts_count = tag_titles.get(tag_title, 0)
                tag_titles[tag_title] = posts_count + 1

        for tag in tags:
            actual_posts_count = tag_titles.get(tag.title, 0) # how many posts have this tag now
            if actual_posts_count != tag.posts_count:
                # quantity of posts with this tag changed
                if actual_posts_count == 0:
                    tag.delete()
                else:
                    tag.posts_count = actual_posts_count
                    tag.put()
            try:
                del tag_titles[tag.title] # we already done with this tag
            except KeyError:
                pass

        for (tag_title, posts_count) in tag_titles.items(): # we got some new tags
            tag = Tag(title = tag_title, posts_count = posts_count)
            tag.put()

class ShowTagHandler(AbstractRequestHandler):

    def get(self, tag_id):
        try:
            tag = Tag.get_by_id(int(tag_id))
            if tag:
                total_pages = int(math.ceil(Post.all().filter('tags = ', tag.title).count() / float(POSTS_PER_PAGE)))
                page = self.request.get_range('page', min_value = 1, max_value = total_pages, default = 1)
                posts = Post.all().filter('tags = ', tag.title).order('-created').fetch(POSTS_PER_PAGE,
                                                                                        (page - 1) * POSTS_PER_PAGE)        
                self.render_template('posts.html', {'posts': posts,
                                                    'title': "All posts with tag \"%s\"" % tag.title,
                                                    'path': self.request.path,
                                                    'page': page,
                                                    'total_pages': total_pages})
            else:
                raise db.BadKeyError()
        except db.BadKeyError:
            self.error(404)
            self.render_template('page_not_found.html')


class RssHandler(webapp.RequestHandler):

    def get(self):
        posts = Post.all().order('-created')
        pub_date = Post.all().order('-created').fetch(1)[0].created
        
        self.response.headers['Content-Type'] = 'application/rss+xml'
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'rss.xml')
        self.response.out.write(template.render(template_path,
                                                {'blog_title': BLOG_TITLE,
                                                 'host': self.request.headers.get('host'),
                                                 'posts': posts,
                                                 'pub_date': pub_date}))
        

class SitemapHandler(webapp.RequestHandler):

    def get(self):
        posts = Post.all()
        tags = Tag.all()

        self.response.headers['Content-Type'] = 'text/xml'
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'sitemap.xml')
        self.response.out.write(template.render(template_path,
                                                {'host': self.request.headers.get('host'),
                                                 'posts': posts,
                                                 'tags': tags}))

class NotFoundPageHandler(AbstractRequestHandler):

    def get(self):
        self.error(404)
        self.render_template('page_not_found.html')

    def post(self):
        self.error(404)
        self.render_template('page_not_found.html')

application = webapp.WSGIApplication([('/', MainPage),
                                      ('/rss.xml', RssHandler),
                                      ('/sitemap.xml', SitemapHandler),
                                      ('/posts/new', NewPostHandler),
                                      ('/posts/edit/(\d+)', EditPostHandler),
                                      ('/posts/(\d+).*', ShowPostHandler),
                                      ('/tags/update', UpdateTagsHandler),
                                      ('/tags/(\d+).*', ShowTagHandler),
                                      ('/.*', NotFoundPageHandler)],
                                     debug = True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
