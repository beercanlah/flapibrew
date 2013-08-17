import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import json
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from cStringIO import StringIO

matplotlib.use("Agg")


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

    string = "data:image/png;base64,"
    string += data
    return string


class PlotUpdate(object):

    def __init__(self, string):
        self.event_name = "plot_update"
        self.data = {
            "msg": "Hallo",
            "img_string": string,
        }

    def to_message(self):
        msg = json.dumps(
            {
                "event": self.event_name,
                "data": self.data,
            }
        )
        return msg


class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print "Websocket opened"
        callback = tornado.ioloop.PeriodicCallback(self.test, 1000)
        callback.start()

    def on_message(self, message):
        self.write_message("You said: " + message)

    def on_close(self):
        print "WebSocket closed"

    def test(self):
        msg = PlotUpdate(generate_test_plot()).to_message()
        print msg
        self.write_message(msg)

application = tornado.web.Application([
    (r'/ws', WSHandler),
])


if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(5050)
    tornado.ioloop.IOLoop.instance().start()
