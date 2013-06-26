# -*- coding: utf-8 -*-
import atexit
from tornado import web, ioloop
from sockjs.tornado import SockJSRouter, SockJSConnection
import logging

import zmq.eventloop
from zmq.eventloop.zmqstream import ZMQStream
import json
import os

zmq.eventloop.ioloop.install()
zmq.eventloop.ioloop.gen_log = logging.getLogger()
zmq.eventloop.ioloop.os = os


zmq_ctx = zmq.Context()
zmq_endpoint = "tcp://localhost:5556"

class TickerConnection(SockJSConnection):
    def _zmq_msg(self, msg):
        logging.info(msg)
        try:
            msg_obj = json.loads(msg[0])
            logging.info(msg_obj)
            if 'group_id' in msg_obj and msg_obj['group_id'] == self.group:
                self.send(msg_obj)
        except Exception as ex:
            logging.error(ex)
        
    def on_open(self, info):
        logging.info("Ticker open: "+self.group)
        zmq_socket = zmq_ctx.socket(zmq.SUB)
        zmq_socket.setsockopt(zmq.SUBSCRIBE, '')
        zmq_socket.connect(zmq_endpoint)
        self.stream = ZMQStream(zmq_socket)
        self.stream.on_recv(self._zmq_msg)

    def on_close(self):
        logging.info("Ticker close: "+self.group)
        self.stream.stop_on_recv()


class UpdateGetHandler(web.RequestHandler):
    
    def __init__(self, app, req, **kwargs):
        super(UpdateGetHandler, self).__init__(app, req, **kwargs)
        self.registered_tickers = {}
    
    def _make_ticker_class(self, **kwargs):
        class_name = str.format("Ticker_{0}", kwargs['group'])
        logging.info("Ticker make: "+kwargs['group'])
        return type(class_name, (TickerConnection,), dict(**kwargs))
    
    def _make_or_get_ticker(self, group):
        if group not in self.registered_tickers:
            srv_url = str.format('/update/{0}', group)
            TickerRouter = SockJSRouter(self._make_ticker_class(group=group), srv_url)
            self.application.add_handlers(".*$", TickerRouter.urls)
            self.registered_tickers[group] = (TickerRouter, srv_url)
            return srv_url
        else:
            return self.registered_tickers[group][1]
    
    def get(self, params):
        #logging.info(self.path_args)
        parameters = params.split('/')
        #logging.info(parameters)
        group = parameters[0]
        ticker_url = self._make_or_get_ticker(group)
        red_url = str.format('{0}/{1}', ticker_url, '/'.join(parameters[1:]))
        self.redirect(red_url)


class TestMainHandler(web.RequestHandler):
    def get(self, group):
        self.render("test.html", group=group)

zmq_test_socket = None
#zmq_test_socket = zmq_ctx.socket(zmq.PUB)
#zmq_test_socket.bind('tcp://lo:5556')
class TestMsgHandler(web.RequestHandler):
    n = 0
    def get(self, group):
        obj = {'msg': 'test', 'group_id': group, 'n': TestMsgHandler.n}
        if zmq_test_socket:
            zmq_test_socket.send_json(obj)
        self.write(str.format("sent n: {0} group: {1}", TestMsgHandler.n, group))
        TestMsgHandler.n += 1

def exit_func(zmq_ctx):
    
    zmq_ctx.destroy()

if __name__ == '__main__':

    logging.getLogger().setLevel(logging.DEBUG)
    atexit.register(exit_func)
    
    app = web.Application(#TickerRouter.urls +
                          [("/test/(.+)", TestMainHandler), 
                           ("/update/(.+)", UpdateGetHandler),
                           ("/send_test_msg/(.+)", TestMsgHandler)],
                          debug=True, template_path="templates"
                          )

    app.listen(8081)
    logging.info(" [*] Listening on 0.0.0.0:8081")
    ioloop.IOLoop.instance().start()
    
    
    