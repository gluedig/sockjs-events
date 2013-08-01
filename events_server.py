# -*- coding: utf-8 -*-
from tornado import web, ioloop
from sockjs.tornado import SockJSRouter, SockJSConnection
import logging

import zmq.eventloop
from zmq.eventloop.zmqstream import ZMQStream
import json
import os
import argparse

zmq.eventloop.ioloop.install()
zmq.eventloop.ioloop.gen_log = logging.getLogger()
zmq.eventloop.ioloop.os = os

zmq_local_endpoint = "inproc://#events"
service_url = "http://gluedig.dnsd.info:443"

class GroupEvents(SockJSConnection):
    def _zmq_msg(self, msg):
        logging.debug(msg)
        try:
            msg_obj = json.loads(msg[0])
            logging.debug(msg_obj)
            if 'group_id' in msg_obj and msg_obj['group_id'] == self.group:
                self.send(msg_obj)
        except Exception as ex:
            logging.error(ex)
        
    def on_open(self, info):
        logging.debug("Group ticker open: "+self.group)
        zmq_socket = zmq.Context.instance().socket(zmq.SUB)
        zmq_socket.connect(zmq_local_endpoint)
        zmq_socket.setsockopt(zmq.SUBSCRIBE, '')
        
        self.stream = ZMQStream(zmq_socket)
        self.stream.on_recv(self._zmq_msg)

    def on_close(self):
        logging.debug("Group ticker close: "+self.group)
        self.stream.stop_on_recv()


class GroupGetHandler(web.RequestHandler):
    
    def __init__(self, app, req, **kwargs):
        super(GroupGetHandler, self).__init__(app, req, **kwargs)
        self.registered_tickers = {}
    
    def _make_ticker_class(self, **kwargs):
        class_name = str.format("GroupTicker_{0}", kwargs['group'])
        logging.debug("Group ticker make: "+kwargs['group'])
        return type(class_name, (GroupEvents,), dict(**kwargs))
    
    def _make_or_get_ticker(self, group):
        if group not in self.registered_tickers:
            srv_url = str.format('/group/{0}', group)
            TickerRouter = SockJSRouter(self._make_ticker_class(group=group), srv_url)
            self.application.add_handlers(".*$", TickerRouter.urls)
            self.registered_tickers[group] = (TickerRouter, srv_url)
            return srv_url
        else:
            return self.registered_tickers[group][1]
    
    def get(self, params):
        #logging.debug(self.path_args)
        parameters = params.split('/')
        #logging.debug(parameters)
        group = parameters[0]
        ticker_url = self._make_or_get_ticker(group)
        red_url = str.format('{0}/{1}', ticker_url, '/'.join(parameters[1:]))
        self.redirect(red_url)

class MonitorEvents(SockJSConnection):
    def _zmq_msg(self, msg):
        #logging.debug(msg)
        try:
            msg_obj = json.loads(msg[0])
            logging.debug(msg_obj)
            if self.monitor != 'All':
                if 'mon_id' in msg_obj and msg_obj['mon_id'] == self.monitor:
                    self.send(msg_obj)
            else:
                self.send(msg_obj)
        except Exception as ex:
            logging.error(ex)
        
    def on_open(self, info):
        logging.debug("Monitor ticker open: "+self.monitor)
        zmq_socket = zmq.Context.instance().socket(zmq.SUB)
        zmq_socket.connect(zmq_local_endpoint)
        zmq_socket.setsockopt(zmq.SUBSCRIBE, '')
        
        self.stream = ZMQStream(zmq_socket)
        self.stream.on_recv(self._zmq_msg)

    def on_close(self):
        logging.debug("Monitor ticker close: "+self.monitor)
        self.stream.stop_on_recv()

class MonitorGetHandler(web.RequestHandler):
    
    def __init__(self, app, req, **kwargs):
        super(MonitorGetHandler, self).__init__(app, req, **kwargs)
        self.registered_tickers = {}
    
    def _make_ticker_class(self, **kwargs):
        class_name = str.format("MonitorTicker_{0}", kwargs['monitor'])
        logging.debug("Monitor ticker make: "+kwargs['monitor'])
        return type(class_name, (MonitorEvents,), dict(**kwargs))
    
    def _make_or_get_ticker(self, monitor):
        if monitor not in self.registered_tickers:
            srv_url = str.format('/monitor/{0}', monitor)
            TickerRouter = SockJSRouter(self._make_ticker_class(monitor=monitor), srv_url)
            self.application.add_handlers(".*$", TickerRouter.urls)
            self.registered_tickers[monitor] = (TickerRouter, srv_url)
            return srv_url
        else:
            return self.registered_tickers[monitor][1]
    
    def get(self, params):
        #logging.info(self.path_args)
        parameters = params.split('/')
        #logging.info(parameters)
        monitor = parameters[0]
        ticker_url = self._make_or_get_ticker(monitor)
        red_url = str.format('{0}/{1}', ticker_url, '/'.join(parameters[1:]))
        self.redirect(red_url)


#===============================================================================
# test handlers
#===============================================================================

class TestMainHandler(web.RequestHandler):
    def get(self, evtype, param):
        if evtype == 'group':
            self.render("test_group.html", group=param, url=service_url)
        elif evtype == 'monitor':
            self.render("test_mon.html", monitor=param, url=service_url)

zmq_test_socket = None

class GroupTestMsgHandler(web.RequestHandler):
    n = 0
    def get(self, group):
        obj = {'msg': 'test', 'group_id': group, 'n': GroupTestMsgHandler.n}
        if zmq_test_socket:
            zmq_test_socket.send_json(obj)
        self.write(str.format("sent n: {0} group: {1}", GroupTestMsgHandler.n, group))
        GroupTestMsgHandler.n += 1
        
class MonitorTestMsgHandler(web.RequestHandler):
    n = 0
    def get(self, mac):
        obj = {'msg': 'test', 'mac': mac, 'n': MonitorTestMsgHandler.n}
        if zmq_test_socket:
            zmq_test_socket.send_json(obj)
        self.write(str.format("sent n: {0} mac: {1}", MonitorTestMsgHandler.n, mac))
        MonitorTestMsgHandler.n += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--test_page', help='provide test page', action='store_true')
    parser.add_argument('--test_sender', help='provide test sender', action='store_true')
    parser.add_argument('--debug', help='print debug info', action='store_true', default=False)
    parser.add_argument('--port', help='application port default: %(default)s', default=8081, type=int)
    parser.add_argument('--url', help='test pages service url: %(default)s', default=service_url)
    parser.add_argument('remote', nargs='?', help='ZMQ event source endpoint default: %(default)s', default="tcp://localhost:5555")

    args = parser.parse_args()
    
    logging.getLogger().setLevel(logging.INFO)
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    handlers = [("/monitor/(.+)", MonitorGetHandler),
                ("/group/(.+)", GroupGetHandler)]
    
    service_url = args.url
    
    if args.test_sender:
        logging.info("Running with test sender")
        zmq_test_socket = zmq.Context.instance().socket(zmq.PUB)
        zmq_test_socket.bind(zmq_local_endpoint)
        test_handlers = [
                ("/send_test_group_msg/(.+)", GroupTestMsgHandler),
                ("/send_test_monitor_msg/(.+)", MonitorTestMsgHandler)]
        handlers += test_handlers
    else:
        if args.test_page:
            logging.info("Running with test page")
            handlers += [("/test/(.+)/(.+)", TestMainHandler)]
            
        logging.info("Connecting to ZMQ endpoint: "+args.remote)
        pd = zmq.devices.ThreadProxy(zmq.SUB, zmq.PUB)
        pd.connect_in(args.remote)
        pd.bind_out(zmq_local_endpoint)
        pd.setsockopt_in(zmq.SUBSCRIBE, '')
        pd.start()
    
    app = web.Application(handlers,
                          debug=args.debug,
                          template_path="templates")

    app.listen(args.port)
    logging.info(str.format("SockJS services listening on 0.0.0.0:{0}", args.port))
    ioloop.IOLoop.instance().start()
    
    
    