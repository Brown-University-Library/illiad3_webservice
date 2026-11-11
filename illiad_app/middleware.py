"""
Preserves equivalent UTF-8 form encodings and explains rejected encodings safely.
"""

import codecs

from django.core.exceptions import BadRequest
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.utils.deprecation import MiddlewareMixin

DJANGO_FORM_ENCODING_ERROR = (
    "HTTP requests with the 'application/x-www-form-urlencoded' content type must be UTF-8 encoded."
)


class FormEncodingMiddleware(MiddlewareMixin):
    """
    Accepts UTF-8 charset aliases and explains Django's other form charset rejections.
    """

    def process_request(self, request: HttpRequest) -> None:
        """
        Normalizes equivalent UTF-8 names without reading or changing the form body.
        Called by: Django's request middleware handling.
        """
        encoding = request.encoding
        if request.method == 'POST' and request.content_type == 'application/x-www-form-urlencoded' and encoding is not None:
            try:
                canonical_encoding = codecs.lookup(encoding).name
            except LookupError:
                canonical_encoding = None
            if canonical_encoding == 'utf-8':
                request.encoding = 'utf-8'

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """
        Returns encoding instructions only for the framework's specific charset error.
        Called by: Django's view exception handling.
        """
        response = None
        encoding = request.encoding
        ## Match the framework message so unrelated BadRequest errors keep their normal handling.
        if (
            isinstance(exception, BadRequest)
            and str(exception) == DJANGO_FORM_ENCODING_ERROR
            and request.method == 'POST'
            and request.content_type == 'application/x-www-form-urlencoded'
            and encoding is not None
            and encoding.lower() != 'utf-8'
        ):
            response = HttpResponseBadRequest(
                b'Bad Request: Send application/x-www-form-urlencoded data encoded as UTF-8. '
                b'Omit the charset parameter from Content-Type, or use charset=UTF-8.',
                content_type='text/plain; charset=utf-8',
            )
        return response
