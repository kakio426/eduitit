import logging
import threading


_request_local = threading.local()


def set_current_request_id(request_id):
    _request_local.request_id = request_id


def get_current_request_id():
    return getattr(_request_local, "request_id", "-")


def clear_current_request_id():
    _request_local.request_id = "-"


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_current_request_id()
        return True
