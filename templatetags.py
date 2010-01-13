from google.appengine.ext.webapp import template

register = template.create_template_register()

@register.simple_tag
def pagination(path, page, total_pages):
    if total_pages < 2:
        return ''
    else:
        page_links = ''
        for p in range(1, total_pages + 1):
            if p == page:
                page_links += '<li>Page %d</li>' % p
            else:
                page_links += '<li><a href="%s?page=%d">Page %d</a></li>' % (path, p, p)
        return '<ul class="pages">' + ''.join(page_links) + '</ul>'
