timeout = 60  # Increased to handle cold starts and scheduler jobs
workers = 1   # Single worker to stay within 512MB
worker_connections = 1000
loglevel = 'info'
errorlog = '-'  # Log to stderr
accesslog = '-' # Log to stderr
