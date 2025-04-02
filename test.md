[2025-04-02 19:32:42 +0000] [16] [ERROR] Error handling request /llm/conversation/chat
Traceback (most recent call last):
File "/usr/local/lib/python3.11/site-packages/gunicorn/workers/sync.py", line 134, in handle
self.handle_request(listener, req, client, addr)
File "/usr/local/lib/python3.11/site-packages/gunicorn/workers/sync.py", line 177, in handle_request
respiter = self.wsgi(environ, resp.start_response)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/flask/app.py", line 1536, in __call__
return self.wsgi_app(environ, start_response)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/flask/app.py", line 1511, in wsgi_app
response = self.full_dispatch_request()
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/flask/app.py", line 917, in full_dispatch_request
rv = self.dispatch_request()
^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/flask/app.py", line 902, in dispatch_request
return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args) # type: ignore[no-any-return]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/app/apis/utils/logMiddleware.py", line 87, in decorated_function
response = f(*args, **kwargs)
^^^^^^^^^^^^^^^^^^
File "/app/apis/utils/balanceMiddleware.py", line 77, in decorated_function
return f(*args, **kwargs)
^^^^^^^^^^^^^^^^^^
File "/app/apis/llm_conversation/conversation.py", line 334, in create_chat_route
llm_response = requests.post(
^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/api.py", line 115, in post
return request("post", url, data=data, json=json, **kwargs)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/api.py", line 59, in request
return session.request(method=method, url=url, **kwargs)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/sessions.py", line 589, in request
resp = self.send(prep, **send_kwargs)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/sessions.py", line 724, in send
history = [resp for resp in gen]
^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/sessions.py", line 724, in <listcomp>
history = [resp for resp in gen]
^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/sessions.py", line 265, in resolve_redirects
resp = self.send(
^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/sessions.py", line 703, in send
r = adapter.send(request, **kwargs)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/requests/adapters.py", line 667, in send
resp = conn.urlopen(
^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/urllib3/connectionpool.py", line 787, in urlopen
response = self._make_request(
^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/urllib3/connectionpool.py", line 534, in _make_request
response = conn.getresponse()
^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/urllib3/connection.py", line 516, in getresponse
httplib_response = super().getresponse()
^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/http/client.py", line 1395, in getresponse
response.begin()
File "/usr/local/lib/python3.11/http/client.py", line 325, in begin
version, status, reason = self._read_status()
^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/http/client.py", line 286, in _read_status
line = str(self.fp.readline(_MAXLINE + 1), "iso-8859-1")
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/socket.py", line 718, in readinto
return self._sock.recv_into(b)
^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/ssl.py", line 1314, in recv_into
return self.read(nbytes, buffer)
^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/ssl.py", line 1166, in read
return self._sslobj.read(len, buffer)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/gunicorn/workers/base.py", line 204, in handle_abort
sys.exit(1)
SystemExit: 1