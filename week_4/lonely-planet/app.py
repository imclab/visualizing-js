#!/usr/bin/env python
import tornado.web
import tornado.httpserver
import tornado.httputil
import tornado.auth
import twitstream
from tornado import websocket
import os

GLOBALS={
    'sockets': [],
    'users' : []
}

(options, args) = twitstream.parser.parse_args()

options.engine = 'tornado'    
options.username = 'lonely_tweet'
options.password = 'so_ronely'

twitUser = None 
authenticated = False

if len(args) < 1:
    twitstream.parser.error("requires one method argument")
else:
    method = args[0]
    if method not in twitstream.GETMETHODS and method not in twitstream.POSTPARAMS:
        raise NotImplementedError("Unknown method: %s" % method)

twitstream.ensure_credentials(options)

def testFunction(status):
    if "user" not in status:
        try:
            if options.debug:
                print >> sys.stderr, status
            return
        except:
            pass

    if len(GLOBALS['sockets']) > 0:
        for socket in GLOBALS['sockets']:
            socket.write_message(status)            
            # print "%s:\t%s\n" % (status.get('user', {}).get('screen_name'), status.get('text'))	


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('home.html')

class MainHandler(tornado.web.RequestHandler):
    def get(self):   
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Allow-Methods", "GET")        

        # global authenticated
        # if authenticated:
        #     auth = "yerp"
        # else:  
        #     auth = "nope"

        # authenticated = False

        test = self.get_secure_cookie('oauth_token')        
        self.render( 'index.html', authenticated = test ) 


class ClientSocket(websocket.WebSocketHandler):
    def open(self):
        GLOBALS['sockets'].append(self)
        global twitUser
        if twitUser != None:                
            GLOBALS['users'].append(twitUser)
        print "WebSocket opened"

    def on_close(self):
        print "WebSocket closed"
        GLOBALS['sockets'].remove(self)


class Announcer(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        data = self.get_argument('data')
        for socket in GLOBALS['sockets']:
            socket.write_message(data)
        self.write('Posted')
  

class TwitterHandler(tornado.web.RequestHandler,
                     tornado.auth.TwitterMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("oauth_token", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authorize_redirect()

    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Twitter auth failed")

        self.set_secure_cookie('user_id', str(user['id'])) 
        self.set_secure_cookie('oauth_token', user['access_token']['key']) 
        self.set_secure_cookie('oauth_secret', user['access_token']['secret'])

        self.set_header("Access-Control-Allow-Origin", "http://localhost:8000")
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.render( 'index.html', authenticated=auth )
        

class PostHandler(tornado.web.RequestHandler, tornado.auth.TwitterMixin):
    @tornado.web.asynchronous
    def post(self):
        oAuthToken = self.get_secure_cookie('oauth_token')
        oAuthSecret = self.get_secure_cookie('oauth_secret') 
        userID = self.get_secure_cookie('user_id')

        if oAuthToken and oAuthSecret:  
            accessToken = {
                'key': oAuthToken,
                'secret': oAuthSecret 
            }
            self.twitter_request(
                "/statuses/update",
                post_args={"status": "Testing 128 thousamn"},
                access_token=accessToken,
                callback=self.async_callback(self._on_post))

    def _on_post(self, new_entry):
        if not new_entry:
            # Call failed; perhaps missing permission?
            self.authorize_redirect()
            return
        self.finish("Posted a message!")

stream = twitstream.twitstream(method, options.username, options.password, testFunction, 
            defaultdata=args[1:], debug=options.debug, engine=options.engine)   

settings = dict(
    twitter_consumer_key='EGLC7uXFL0wNMygeZoZOTw',
    twitter_consumer_secret='pnvNerZKSBSw1kri5wjaM255CluYwd3OdaovUeyCsI',
    cookie_secret='NTliOTY5NzJkYTVlMTU0OTAwMTdlNjgzMTA5M2U3OGQ5NDIxZmU3Mg==',
    template_path=os.path.join( os.path.dirname( __file__ ), 'templates'),            
)

if __name__ == "__main__":

	app = tornado.web.Application(
		handlers = [
            (r"/", IndexHandler),
            (r"/home", MainHandler),
            (r"/login", TwitterHandler),
            (r"/post", PostHandler),
            (r"/socket", ClientSocket),
            (r"/push", Announcer),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "./static"}), 
        ], 
        **settings
	)
	http_server = tornado.httpserver.HTTPServer(app)
	http_server.listen(8000)
	stream.run()
