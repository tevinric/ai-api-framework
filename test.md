[2025-04-03 17:37:32 +0000] [1] [CRITICAL] WORKER TIMEOUT (pid:6)
[2025-04-03 17:37:32 +0000] [6] [ERROR] Error handling request /image-generation/dalle3
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
File "/app/apis/image_generation/dalle3.py", line 293, in custom_image_generation_route
response = client.images.generate(
^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/resources/images.py", line 264, in generate
return self._post(
^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 1242, in post
return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 919, in request
return self._request(
^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 1008, in _request
return self._retry_request(
^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 1057, in _retry_request
return self._request(
^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 955, in _request
response = self._client.send(
^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 928, in send
raise exc
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 922, in send
response.read()
File "/usr/local/lib/python3.11/site-packages/httpx/_models.py", line 881, in read
self._content = b"".join(self.iter_bytes())
^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_models.py", line 897, in iter_bytes
for raw_bytes in self.iter_raw():
File "/usr/local/lib/python3.11/site-packages/httpx/_models.py", line 951, in iter_raw
for raw_stream_bytes in self.stream:
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 153, in __iter__
for chunk in self._stream:
File "/usr/local/lib/python3.11/site-packages/httpx/_transports/default.py", line 127, in __iter__
for part in self._httpcore_stream:
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/connection_pool.py", line 407, in __iter__
raise exc from None
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/connection_pool.py", line 403, in __iter__
for part in self._stream:
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 342, in __iter__
raise exc
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 334, in __iter__
for chunk in self._connection._receive_response_body(**kwargs):
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 203, in _receive_response_body
event = self._receive_event(timeout=timeout)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 217, in _receive_event
data = self._network_stream.read(
^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpcore/_backends/sync.py", line 128, in read
return self._sock.recv(max_bytes)
^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/ssl.py", line 1295, in recv
return self.read(buflen)
^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/ssl.py", line 1168, in read
return self._sslobj.read(len)
^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/gunicorn/workers/base.py", line 204, in handle_abort
sys.exit(1)
SystemExit: 1
[2025-04-03 17:37:32 +0000] [6] [INFO] Worker exiting (pid: 6)
[2025-04-03 17:37:33 +0000] [11] [INFO] Booting worker with pid: 11