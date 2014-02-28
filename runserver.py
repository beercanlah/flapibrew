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
from contextlib import closing

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
        self.pid_controlled = False
        self.duty_cycle = 0
        self.pvalue = 0.11
        self.ivalue = 10
        self.heater = False
        self.setpoint = 25.0

    @property
    def temperature(self):
        temp = 25.0 + float(np.random.normal(0, 2, [1, 1])[0])
        temp = np.round(temp, 2)
        return temp

    def update(self):
        pass


class YunBrewery(object):

    def __init__(self, ip):
        self.url = 'http://' + ip
        self.update

    def update(self):
        r = requests.get(self.url + '/data/get')
        data = json.loads(r.text)
        status = data['value']
        self.temperature = float(status['temperature'])
        self.heater = bool(int(status['heater']))
        self._pump_on = bool(int(status['pump']))
        self._pid_controlled = bool(int(status['pid']))
        self._duty_cycle = float(status['dutycycle'])
        self._ivalue = float(status['ivalue'])
        self._pvalue = float(status['pvalue'])
        self._setpoint = float(status['setpoint'])

    @property
    def pump_on(self):
        return self._pump_on

    @pump_on.setter
    def pump_on(self, value):
        self._yun_command('/pump/' + str(int(value)))

    @property
    def pid_controlled(self):
        return self._pid_controlled

    @pid_controlled.setter
    def pid_controlled(self, value):
        self._yun_command('/pid/' + str(int(value)))

    @property
    def duty_cycle(self):
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value):
        self._yun_command('/heater/' + str(value))

    @property
    def ivalue(self):
        return self._ivalue

    @ivalue.setter
    def ivalue(self, value):
        self._yun_command('/ivalue/' + str(value))

    @property
    def pvalue(self):
        return self._pvalue

    @pvalue.setter
    def pvalue(self, value):
        self._yun_command('/pvalue/' + str(value))

    @property
    def setpoint(self):
        return self._setpoint

    @setpoint.setter
    def setpoint(self, value):
        self._yun_command('/setpoint/' + str(value))

    def _yun_command(self, command):
        call = self.url + '/arduino' + command
        print call
        requests.get(call)

        
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
    fig.close()

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
            'plotting': self._plotting,
            'backend': self._backend,
            'pump': self._pump,
            'pid': self._pid,
            'dutycycle': self._dutycycle,
            'pvalue': self._pvalue,
            'ivalue': self._ivalue,
            'setpoint': self._setpoint
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
        global log
        if hasattr(self, 'plot_callback'):
            self.plot_callback.stop()
        if hasattr(self, 'status_callback'):
            self.status_callback.stop()
            log = None
        print 'WebSocket closed'

    def test(self):
        msg = PlotUpdate(generate_temp_plot()).to_message()
        self.write_message(msg)

    def status(self):
        global log
        timestamp = datetime.datetime.now()

        self.brewery.update()

        temperature = self.brewery.temperature
        pump_state = 'on' if self.brewery.pump_on else 'off'
        duty_cycle = str(self.brewery.duty_cycle)
        pid_state = 'on' if self.brewery.pid_controlled else 'off'
        pvalue = str(self.brewery.pvalue)
        ivalue = str(self.brewery.ivalue)
        heater = 'on' if self.brewery.heater else 'off'
        setpoint = str(self.brewery.setpoint)

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
                    'heater': heater,
                    'pump_state': pump_state,
                    'duty_cycle': duty_cycle,
                    'pid_state': pid_state,
                    'pvalue': pvalue,
                    'ivalue': ivalue,
                    'setpoint': setpoint,
                }
            }
        )

        print msg

        self.write_message(msg)

    def _plotting(self, data):
        if (data['state'] == 'on'):
            self.plot_callback.start()
        elif (data['state'] == 'off'):
            self.plot_callback.stop()

    def _backend(self, data):
        if (data['port'] == 'dummy'):
            self.brewery = DummyBrewery()
            self.status_callback.start()
        else:
            self.brewery = YunBrewery(data['port'])
            self.status_callback.start()

    def _pump(self, data):
        if data['action'] == 'toggle':
            self.brewery.pump_on = not self.brewery.pump_on

    def _pid(self, data):
        if data['action'] == 'toggle':
            self.brewery.pid_controlled = not self.brewery.pid_controlled

    def _dutycycle(self, data):
        self.brewery.duty_cycle = int(data['dutycycle'])

    def _pvalue(self, data):
        self.brewery.pvalue = float(data['pvalue'])

    def _ivalue(self, data):
        self.brewery.ivalue = float(data['ivalue'])

    def _setpoint(self, data):
        self.brewery.setpoint = float(data['setpoint'])


tr = WSGIContainer(app)

application = tornado.web.Application([
    (r'/ws', WSHandler),
    (r".*", tornado.web.FallbackHandler, dict(fallback=tr)),
])

log = None


if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(5050)
    tornado.ioloop.IOLoop.instance().start()
