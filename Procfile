# ROLLBACK: gunicorn config.wsgi --workers 3 --threads 4 --worker-class gthread --log-file - --log-level info --access-logfile - --timeout 120
web: python3 manage.py bootstrap_runtime && uvicorn config.asgi:application --host 0.0.0.0 --port $PORT --workers 2 --loop uvloop --http httptools --timeout-keep-alive 120
