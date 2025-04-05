[2025-04-05 17:13:03 +0000] [1] [CRITICAL] WORKER TIMEOUT (pid:6)
[2025-04-05 17:13:03 +0000] [6] [ERROR] Error handling request /docint/summarization
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
File "/app/apis/document_intelligence/summarization.py", line 1415, in document_summarization_route
summary_result = chunk_and_summarize(text_content, total_pages, summary_options)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/app/apis/document_intelligence/summarization.py", line 682, in chunk_and_summarize
response = gpt4o_service(
^^^^^^^^^^^^^^
File "/app/apis/utils/llmServices.py", line 177, in gpt4o_service
response = openai_client.chat.completions.create(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_utils/_utils.py", line 279, in wrapper
return func(*args, **kwargs)
^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/resources/chat/completions/completions.py", line 914, in create
return self._post(
^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 1242, in post
return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 919, in request
return self._request(
^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/openai/_base_client.py", line 955, in _request
response = self._client.send(
^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 914, in send
response = self._send_handling_auth(
^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 942, in _send_handling_auth
response = self._send_handling_redirects(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 979, in _send_handling_redirects
response = self._send_single_request(request)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_client.py", line 1014, in _send_single_request
response = transport.handle_request(request)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpx/_transports/default.py", line 250, in handle_request
resp = self._pool.handle_request(req)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/connection_pool.py", line 256, in handle_request
raise exc from None
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/connection_pool.py", line 236, in handle_request
response = connection.handle_request(
^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/connection.py", line 103, in handle_request
return self._connection.handle_request(request)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 136, in handle_request
raise exc
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 106, in handle_request
) = self._receive_response_headers(**kwargs)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/usr/local/lib/python3.11/site-packages/httpcore/_sync/http11.py", line 177, in _receive_response_headers
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