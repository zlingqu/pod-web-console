from werkzeug import serving
from app import app
from app import route
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

@serving.run_with_reloader
def run_server():
    app.debug = True

    server = pywsgi.WSGIServer(
        listener = ('0.0.0.0', 8800),
        application=app,
        handler_class=WebSocketHandler)
    server.serve_forever()

if __name__ == '__main__':
    run_server()
