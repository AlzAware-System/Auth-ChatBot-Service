import uuid
import logging
import json
import os
from datetime import datetime
import requests

class JSONFormatter(logging.Formatter):
    def __init__(self, service_name):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        correlation_id = os.environ.get("CORRELATION_ID", "N/A")
        try:
            from flask import has_app_context, g
            if has_app_context() and hasattr(g, "correlation_id"):
                correlation_id = g.correlation_id
        except ImportError:
            pass

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "correlation_id": correlation_id,
            "message": record.getMessage()
        }
        return json.dumps(log_data)

def _inject_correlation_id(kwargs):
    headers = kwargs.get('headers', {})
    if headers is None:
        headers = {}
    
    correlation_id = os.environ.get('CORRELATION_ID')
    try:
        from flask import has_app_context, g
        if has_app_context() and hasattr(g, 'correlation_id'):
            correlation_id = g.correlation_id
    except ImportError:
        pass
        
    if correlation_id:
        # Convert dictionary to lower keys for checking
        header_keys = [k.lower() for k in headers.keys()]
        if 'x-correlation-id' not in header_keys:
            headers['X-Correlation-ID'] = correlation_id
        
    kwargs['headers'] = headers
    return kwargs

_original_session_request = requests.Session.request
def _traced_session_request(self, method, url, **kwargs):
    kwargs = _inject_correlation_id(kwargs)
    return _original_session_request(self, method, url, **kwargs)
requests.Session.request = _traced_session_request

_original_post = requests.post
def _traced_post(url, data=None, json=None, **kwargs):
    kwargs = _inject_correlation_id(kwargs)
    return _original_post(url, data=data, json=json, **kwargs)
requests.post = _traced_post

_original_get = requests.get
def _traced_get(url, params=None, **kwargs):
    kwargs = _inject_correlation_id(kwargs)
    return _original_get(url, params=params, **kwargs)
requests.get = _traced_get

_original_request = requests.request
def _traced_request(method, url, **kwargs):
    kwargs = _inject_correlation_id(kwargs)
    return _original_request(method, url, **kwargs)
requests.request = _traced_request

def setup_tracing(app, service_name):
    from flask import request, g
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter(service_name))
    logger.addHandler(handler)
    
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False

    @app.before_request
    def before_request():
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        g.correlation_id = correlation_id
        app.logger.info(f"Incoming {request.method} {request.path}")

    @app.after_request
    def after_request(response):
        if hasattr(g, 'correlation_id'):
            response.headers["X-Correlation-ID"] = g.correlation_id
        return response

    return logger
