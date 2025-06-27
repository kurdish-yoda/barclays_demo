import os
import sys
import logging
from website import create_app
from pathlib import Path
from secrets import token_hex

def configure_werkzeug_logger(show_log=False):
    log = logging.getLogger('werkzeug')
    if show_log:
        log.setLevel(logging.INFO)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            log.addHandler(handler)
    else:
        log.setLevel(logging.ERROR)
        log.handlers = []
        log.addHandler(logging.NullHandler())

# Set environment variables
os.environ['INSTANCE_ID'] = '0'  # Single instance

os.environ['FLASK_SECRET_KEY'] = token_hex(24)

# Check if 'show_log' argument is provided
show_log = 'show_log' in sys.argv

# Configure Werkzeug logger based on command-line argument
configure_werkzeug_logger(show_log)

# Determine if we're running locally or on Azure
is_azure = os.environ.get('IS_AZURE_ENVIRONMENT', 'false').lower() == 'true'

# SSL certificate paths
current_dir = Path(__file__).resolve().parent
SSL_CERT = current_dir / 'cert.pem'
SSL_KEY = current_dir / 'key.pem'

app = create_app(secret_key=os.environ['FLASK_SECRET_KEY'], instance_id=os.environ['INSTANCE_ID'])

if __name__ == '__main__':
    if is_azure:
        port = int(os.environ.get('PORT', 80))
    else:
        port = 443  # Default HTTPS port

    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    app.logger.info(f"Starting server on port {port}")
    app.logger.info(f"Debug mode: {'On' if debug else 'Off'}")
    app.logger.info(f"Redis URL: {app.config['SESSION_REDIS']}")
    app.logger.info(f"Running on Azure: {is_azure}")
    app.logger.info(f"Werkzeug logging: {'Enabled' if show_log else 'Disabled'}")

    if not is_azure:
        # Running locally, use HTTPS
        if SSL_CERT.exists() and SSL_KEY.exists():
            ssl_context = (str(SSL_CERT), str(SSL_KEY))
            app.logger.info("Running with HTTPS enabled")
            app.run(debug=debug, host="0.0.0.0", port=port, ssl_context=ssl_context)
        else:
            app.logger.error("SSL certificate files not found. Running without HTTPS.")
            app.run(debug=debug, host="0.0.0.0", port=5000)  # Fallback to HTTP on port 5000
    else:
        # Running on Azure, use default (HTTP) as Azure handles HTTPS
        app.run(debug=debug, host="0.0.0.0", port=port)
