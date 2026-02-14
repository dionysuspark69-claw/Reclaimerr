import niquests

RETRY_CODES = (429, 503, 502, 504)


def should_retry_on_status(exception: BaseException) -> bool:
    """Check if exception is a retryable HTTP status code."""
    if isinstance(exception, niquests.HTTPError) and exception.response is not None:
        return exception.response.status_code in RETRY_CODES
    return False
