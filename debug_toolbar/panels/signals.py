from __future__ import unicode_literals

from django.core.signals import (
    request_started, request_finished, got_request_exception)
from django.db.models.signals import (
    class_prepared, pre_init, post_init, pre_save, post_save,
    pre_delete, post_delete, post_syncdb)
from django.dispatch.dispatcher import WEAKREF_TYPES
from django.utils.translation import ugettext_lazy as _, ungettext
from django.utils.importlib import import_module


try:
    from django.db.backends.signals import connection_created
except ImportError:
    connection_created = None

from debug_toolbar.panels import DebugPanel
from debug_toolbar.utils.settings import CONFIG


class SignalDebugPanel(DebugPanel):
    name = "Signals"
    template = 'debug_toolbar/panels/signals.html'
    has_content = True

    SIGNALS = {
        'request_started': request_started,
        'request_finished': request_finished,
        'got_request_exception': got_request_exception,
        'connection_created': connection_created,
        'class_prepared': class_prepared,
        'pre_init': pre_init,
        'post_init': post_init,
        'pre_save': pre_save,
        'post_save': post_save,
        'pre_delete': pre_delete,
        'post_delete': post_delete,
        'post_syncdb': post_syncdb,
    }

    def nav_title(self):
        return _("Signals")

    def nav_subtitle(self):
        signals = self.get_stats()['signals']
        num_receivers = sum(len(s[2]) for s in signals)
        num_signals = len(signals)
        # here we have to handle a double count translation, hence the
        # hard coding of one signal
        if num_signals == 1:
            return ungettext('%(num_receivers)d receiver of 1 signal',
                             '%(num_receivers)d receivers of 1 signal',
                             num_receivers) % {'num_receivers': num_receivers}
        return ungettext('%(num_receivers)d receiver of %(num_signals)d signals',
                         '%(num_receivers)d receivers of %(num_signals)d signals',
                         num_receivers) % {'num_receivers': num_receivers,
                                           'num_signals': num_signals}

    def title(self):
        return _("Signals")

    @property
    def signals(self):
        signals = self.SIGNALS.copy()
        for signal in CONFIG['EXTRA_SIGNALS']:
            mod_path, signal_name = signal.rsplit('.', 1)
            signals_mod = import_module(mod_path)
            signals[signal_name] = getattr(signals_mod, signal_name)
        return signals

    def process_response(self, request, response):
        signals = []
        for name, signal in sorted(self.signals.items(), key=lambda x: x[0]):
            if signal is None:
                continue
            receivers = []
            for (receiverkey, r_senderkey), receiver in signal.receivers:
                if isinstance(receiver, WEAKREF_TYPES):
                    receiver = receiver()
                if receiver is None:
                    continue

                receiver = getattr(receiver, '__wraps__', receiver)
                receiver_name = getattr(receiver, '__name__', str(receiver))
                if getattr(receiver, '__self__', None) is not None:
                    receiver_class_name = getattr(receiver.__self__, '__class__', type).__name__
                    text = "%s.%s" % (receiver_class_name, receiver_name)
                elif getattr(receiver, 'im_class', None) is not None:   # Python 2 only
                    receiver_class_name = receiver.im_class.__name__
                    text = "%s.%s" % (receiver_class_name, receiver_name)
                else:
                    text = "%s" % receiver_name
                receivers.append(text)
            signals.append((name, signal, receivers))

        self.record_stats({'signals': signals})
