from __future__ import unicode_literals

try:
    import resource
except ImportError:
    pass  # Will fail on Win32 systems
import time
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from debug_toolbar.panels import DebugPanel


class TimerDebugPanel(DebugPanel):
    """
    Panel that displays the time a response took in milliseconds.
    """
    name = 'Timer'
    template = 'debug_toolbar/panels/timer.html'

    try:  # if resource module not available, don't show content panel
        resource
    except NameError:
        has_content = False
        has_resource = False
    else:
        has_content = True
        has_resource = True

    def process_request(self, request):
        self._start_time = time.time()
        if self.has_resource:
            self._start_rusage = resource.getrusage(resource.RUSAGE_SELF)

    def process_response(self, request, response):
        stats = {}
        if hasattr(self, '_start_time'):
            stats['total_time'] = (time.time() - self._start_time) * 1000
        if hasattr(self, '_start_rusage'):
            self._end_rusage = resource.getrusage(resource.RUSAGE_SELF)
            stats['utime'] = 1000 * self._elapsed_ru('ru_utime')
            stats['stime'] = 1000 * self._elapsed_ru('ru_stime')
            stats['total'] = stats['utime'] + stats['stime']
            stats['vcsw'] = self._elapsed_ru('ru_nvcsw')
            stats['ivcsw'] = self._elapsed_ru('ru_nivcsw')
            stats['minflt'] = self._elapsed_ru('ru_minflt')
            stats['majflt'] = self._elapsed_ru('ru_majflt')
            # these are documented as not meaningful under Linux.  If you're running BSD
            # feel free to enable them, and add any others that I hadn't gotten to before
            # I noticed that I was getting nothing but zeroes and that the docs agreed. :-(
            #
            #        stats['blkin'] = self._elapsed_ru('ru_inblock')
            #        stats['blkout'] = self._elapsed_ru('ru_oublock')
            #        stats['swap'] = self._elapsed_ru('ru_nswap')
            #        stats['rss'] = self._end_rusage.ru_maxrss
            #        stats['srss'] = self._end_rusage.ru_ixrss
            #        stats['urss'] = self._end_rusage.ru_idrss
            #        stats['usrss'] = self._end_rusage.ru_isrss

        self.record_stats(stats)

    def nav_title(self):
        return _('Time')

    def nav_subtitle(self):
        stats = self.get_stats()

        if hasattr(self, '_start_rusage'):
            utime = self._end_rusage.ru_utime - self._start_rusage.ru_utime
            stime = self._end_rusage.ru_stime - self._start_rusage.ru_stime
            return _('CPU: %(cum)0.2fms (%(total)0.2fms)') % {
                'cum': (utime + stime) * 1000.0,
                'total': stats['total_time']
            }
        elif 'total_time' in stats:
            return _('TOTAL: %0.2fms') % stats['total_time']
        else:
            return ''

    def title(self):
        return _('Time')

    def _elapsed_ru(self, name):
        return getattr(self._end_rusage, name) - getattr(self._start_rusage, name)

    def content(self):
        stats = self.get_stats()
        rows = (
            (_('User CPU time'), _('%(utime)0.3f msec') % stats),
            (_('System CPU time'), _('%(stime)0.3f msec') % stats),
            (_('Total CPU time'), _('%(total)0.3f msec') % stats),
            (_('Elapsed time'), _('%(total_time)0.3f msec') % stats),
            (_('Context switches'), _('%(vcsw)d voluntary, %(ivcsw)d involuntary') % stats),
        )
        context = self.context.copy()
        context.update({'rows': rows})
        return render_to_string(self.template, context)
