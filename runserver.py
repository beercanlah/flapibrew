import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import json
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from cStringIO import StringIO
from collections import namedtuple

matplotlib.use('Agg')

BreweryState = namedtuple('BreweryState',
                          [
                              'pump_on',
                              'recording_data',
                          ]
)


class DummyBrewery(object):

    def get_temperature(self):
        temp = 25.0 + float(np.random.normal(0, 2, [1, 1])[0])
        temp = np.round(temp, 2)
        return temp


def generate_test_plot():
    # Plot sin and cos between -10 and 10 (1000 points)
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    xs = np.linspace(-10, 10, 1000)
    randsin = np.sin(xs) + np.random.normal(0, 0.1, xs.shape)
    ax.plot(xs, randsin, label='sin(x)')
    ax.plot(xs, np.cos(xs), label='cos(x)')
    ax.legend()

    # Encode image to png in base64
    io = StringIO()
    fig.savefig(io, format='png')
    data = io.getvalue().encode('base64')

    string = 'data:image/png;base64,'
    string += data
    return string


class PlotUpdate(object):

    def __init__(self, string):
        self.event_name = 'plot_update'
        self.data = {
            'msg': 'Hallo',
            'img_string': string,
        }

    def to_message(self):
        msg = json.dumps(
            {
                'event': self.event_name,
                'data': self.data,
            }
        )
        return msg


class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):

        # Set up message handler functions, each is a entry in a
        # dictionary, where the key is the event name and the value
        # is the handler function
        self.msg_handler = {
            'plot_request': self._plot_request,
            'backend': self._backend,
        }

        # Set up periodic call back for updating the plot. We don't start
        # the periodic callback yet, this will be done upon request in an
        # event handler
        self.plot_callback = tornado.ioloop.PeriodicCallback(
            self.test,
            2000
        )

        self.status_callback = tornado.ioloop.PeriodicCallback(
            self.status,
            1000
        )

    def on_message(self, message):
        # Parse message and pass on to message handler function
        msg = json.loads(message)
        self.msg_handler[msg['event']](msg['data'])

    def on_close(self):
        self.plot_callback.stop()
        print 'WebSocket closed'

    def test(self):
        msg = PlotUpdate(generate_test_plot()).to_message()
        print msg
        self.write_message(msg)

    def status(self):
        temperature = self.brewery.get_temperature()

        msg = json.dumps(
            {
                'event':  'status_update',
                'data':
                {
                    'temperature': temperature,
                }
            }
        )

        self.write_message(msg)

    def _plot_request(self, data):
        if (not state.recording_data and data['state'] == 'on'):
            self.plot_callback.start()
        elif (state.recording_data and data['state'] == 'off'):
            self.plot_callback.stop()

    def _backend(self, data):
        if (data['port'] == 'dummy'):
            self.brewery = DummyBrewery()
            self.status_callback.start()


application = tornado.web.Application([
    (r'/ws', WSHandler),
])

state = BreweryState(
    pump_on=False,
    recording_data=False,
)


if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(5050)
    tornado.ioloop.IOLoop.instance().start()
