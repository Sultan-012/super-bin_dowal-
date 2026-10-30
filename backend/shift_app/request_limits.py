"""Bound actual ASGI body bytes, including chunked and understated requests."""
import re
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.responses import JSONResponse


class RequestLimits:
    def __init__(self, app, upload_limit):
        self.app = app
        self.normal = RequestBodyLimitMiddleware(app, max_body_size=512 * 1024)
        self.upload = RequestBodyLimitMiddleware(app, max_body_size=upload_limit)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        lengths = [value for name, value in scope.get('headers', []) if name.lower() == b'content-length']
        if len(lengths) > 1 or (lengths and not re.fullmatch(rb'[0-9]+', lengths[0])):
            return await JSONResponse({'message': 'حجم الطلب غير صالح.'}, status_code=400)(scope, receive, send)
        replaced = False

        async def localized_send(message):
            nonlocal replaced
            if message['type'] == 'http.response.start' and message['status'] == 413:
                replaced = True
                await JSONResponse({'message': 'حجم الطلب يتجاوز الحد المسموح.'}, status_code=413)(scope, receive, send)
            elif not replaced:
                await send(message)

        middleware = self.upload if scope.get('path') == '/api/attachments' else self.normal
        await middleware(scope, receive, localized_send)
