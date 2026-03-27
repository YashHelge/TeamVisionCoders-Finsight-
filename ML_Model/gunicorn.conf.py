"""Gunicorn production configuration — 4× Uvicorn workers."""

bind = "0.0.0.0:8080"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
preload_app = False
