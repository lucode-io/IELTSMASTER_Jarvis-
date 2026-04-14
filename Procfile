web: cd bot && gunicorn --bind 0.0.0.0:$PORT --worker-class gthread --threads 4 --timeout 120 main:health_app & python bot/main.py
