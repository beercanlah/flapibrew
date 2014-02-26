import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
from tornado.wsgi import WSGIContainer
import json
import numpy as np
import pandas as pd
import datetime
from cStringIO import StringIO
from collections import namedtuple
from flapibrew import app
import requests

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import MaxNLocator

matplotlib.use('Agg')

BreweryState = namedtuple('BreweryState',
                          [
                              'pump_on',
                              'recording_data',
                          ]
)


class DummyBrewery(object):

    def __init__(self):
        self.pump_on = False
        self.heater_on = False
        self.pid_controlled = False

    @property
    def temperature(self):
        temp = 25.0 + float(np.random.normal(0, 2, [1, 1])[0])
        temp = np.round(temp, 2)
        return temp

    @property
    def full_status(self):
        temperature = self.temperature
        pump_state = 'on' if self.pump_on else 'off'
        heater_state = 'on' if self.heater_on else 'off'
        pid_state = 'on' if self.pid_controlled else 'off'

        return temperature, pump_state, heater_state, pid_state

    def pump(self, action):
        if action == 'toggle':
            self.pump_on = not self.pump_on

    def pid(self, action):
        if action == 'toggle':
            self.pid_controlled = not self.pid_controlled


class YunBrewery(object):

    def __init__(self):
        print 'YunBrewery started'

    @property
    def full_status(self):
        r = requests.get('http://192.168.2.105/data/get')
        data = json.loads(r.text)
        status = data['value']
        temperature = float(status['temperature'])
        pump_state = status['pump']
        heater_state = status['heater']
        pid_state = status['pid']

        return temperature, pump_state, heater_state, pid_state


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


def generate_temp_plot():

    global log

    formatter = DateFormatter("%H:%M:%S")
    locator = MaxNLocator(4)
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_major_locator(locator)
    xs = matplotlib.dates.date2num(log.index)
    ax.plot(xs, log.temperature)

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
            'pump': self._pump,
            'pid': self._pid,
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
        if hasattr(self, 'plot_callback'):
            self.plot_callback.stop()
        if hasattr(self, 'status_callback'):
            self.status_callback.stop()
        print 'WebSocket closed'

    def test(self):
        msg = PlotUpdate(generate_temp_plot()).to_message()
        self.write_message(msg)

    def status(self):
        global log
        timestamp = datetime.datetime.now()
        temperature, pump_state, heater_state, pid_state = self.brewery.full_status

        if log is None:
            log = pd.DataFrame(
                [temperature],
                index=[timestamp],
                columns=['temperature'],
            )
        else:
            new = pd.DataFrame(
                [temperature],
                index=[timestamp],
                columns=['temperature'],
            )
            log = log.append(new)

        msg = json.dumps(
            {
                'event':  'status_update',
                'data':
                {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'temperature': temperature,
                    'pump_state': pump_state,
                    'heater_state': heater_state,
                    'pid_state': pid_state,
                }
            }
        )

        print msg

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

        if (data['port'] == 'yun'):
            self.brewery = YunBrewery()
            self.status_callback.start()

    def _pump(self, data):
        self.brewery.pump(data['action'])

    def _pid(self, data):
        self.brewery.pid(data['action'])

tr = WSGIContainer(app)

application = tornado.web.Application([
    (r'/ws', WSHandler),
    (r".*", tornado.web.FallbackHandler, dict(fallback=tr)),
])

state = BreweryState(
    pump_on=False,
    recording_data=False,
)

log = None


if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(5050)
    tornado.ioloop.IOLoop.instance().start()
