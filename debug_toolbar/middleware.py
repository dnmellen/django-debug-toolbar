"""
Debug Toolbar middleware
"""

from __future__ import unicode_literals

import threading

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.encoding import force_text

from debug_toolbar.toolbar.loader import DebugToolbar
from debug_toolbar.utils.settings import CONFIG

_HTML_TYPES = ('text/html', 'application/xhtml+xml')
# Handles python threading module bug - http://bugs.python.org/issue14308
threading._DummyThread._Thread__stop = lambda x: 1


def replace_insensitive(string, target, replacement):
    """
    Similar to string.replace() but is case insensitive.
    Code borrowed from:
    http://forums.devshed.com/python-programming-11/case-insensitive-string-replace-490921.html
    """
    no_case = string.lower()
    index = no_case.rfind(target.lower())
    if index >= 0:
        return string[:index] + replacement + string[index + len(target):]
    else:  # no results so return the original string
        return string


def show_toolbar(request):
    """
    Default function to determine whether to show the toolbar on a given page.
    """
    if request.META.get('REMOTE_ADDR', None) not in settings.INTERNAL_IPS:
        return False

    return bool(settings.DEBUG)


class DebugToolbarMiddleware(object):
    """
    Middleware to set up Debug Toolbar on incoming request and render toolbar
    on outgoing response.
    """
    debug_toolbars = {}

    def __init__(self):
        # The method to call to decide to show the toolbar
        self.show_toolbar = CONFIG['SHOW_TOOLBAR_CALLBACK'] or show_toolbar

        # The tag to attach the toolbar to
        self.tag = '</%s>' % CONFIG['TAG']

    def process_request(self, request):
        __traceback_hide__ = True                                       # noqa
        if self.show_toolbar(request):
            toolbar = DebugToolbar(request)
            for panel in toolbar.panels:
                panel.enabled = panel.dom_id() not in request.COOKIES
                if not panel.enabled:
                    continue
                panel.enable_instrumentation()
                panel.process_request(request)
            self.__class__.debug_toolbars[threading.current_thread().ident] = toolbar

    def process_view(self, request, view_func, view_args, view_kwargs):
        __traceback_hide__ = True                                       # noqa
        toolbar = self.__class__.debug_toolbars.get(threading.current_thread().ident)
        if not toolbar:
            return
        result = None
        for panel in toolbar.panels:
            if not panel.enabled:
                continue
            response = panel.process_view(request, view_func, view_args, view_kwargs)
            if response:
                result = response
        return result

    def process_response(self, request, response):
        __traceback_hide__ = True                                       # noqa
        ident = threading.current_thread().ident
        toolbar = self.__class__.debug_toolbars.get(ident)
        if not toolbar or request.is_ajax() or getattr(response, 'streaming', False):
            return response
        if isinstance(response, HttpResponseRedirect):
            if not toolbar.config['INTERCEPT_REDIRECTS']:
                return response
            redirect_to = response.get('Location', None)
            if redirect_to:
                cookies = response.cookies
                response = render(
                    request,
                    'debug_toolbar/redirect.html',
                    {'redirect_to': redirect_to}
                )
                response.cookies = cookies
        for panel in toolbar.panels:
            if not panel.enabled:
                continue
            panel.process_response(request, response)
            panel.disable_instrumentation()
        if ('gzip' not in response.get('Content-Encoding', '') and
                response.get('Content-Type', '').split(';')[0] in _HTML_TYPES):
            response.content = replace_insensitive(
                force_text(response.content, encoding=settings.DEFAULT_CHARSET),
                self.tag,
                force_text(toolbar.render_toolbar() + self.tag))
            if response.get('Content-Length', None):
                response['Content-Length'] = len(response.content)
        del self.__class__.debug_toolbars[ident]
        return response
