import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import json


class PlotUpdate(object):

    def __init__(self):
        self.event_name = "plot_update"
        self.data = {
            "msg": "Hallo",
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
        msg = PlotUpdate().to_message()
        print msg
        self.write_message(msg)

    def on_message(self, message):
        self.write_message("You said: " + message)

    def on_close(self):
        print "WebSocket closed"

application = tornado.web.Application([
    (r'/ws', WSHandler),
])


if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(5050)
    tornado.ioloop.IOLoop.instance().start()
