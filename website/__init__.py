from flask import Flask, render_template, session, request, current_app, url_for, redirect, send_from_directory
from flask.sessions import SessionInterface, SessionMixin
from flask_login import LoginManager
from flask_cors import CORS
import os
import logging
from logging.handlers import RotatingFileHandler
import uuid
import redis
from datetime import timedelta, datetime
from itsdangerous import Signer, want_bytes
import json
from user_agents import parse
from werkzeug.middleware.proxy_fix import ProxyFix
from .wix_db import WixDatabase
from .models import User
from .secrets import get_secret
from dotenv import load_dotenv
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from .avatar import animation_bp

load_dotenv()

class RedisSession(dict, SessionMixin):
    def __init__(self, initial=None, sid=None, permanent=False):
        self.sid = sid
        self.permanent = permanent
        if initial:
            super().__init__(initial)
        else:
            super().__init__()

class InstanceAwareRedisSessionInterface(SessionInterface):
    serializer = json
    session_class = RedisSession

    def __init__(self, redis, key_prefix, secret_key, use_signer=False, permanent=False):
        self.redis = redis
        self.key_prefix = key_prefix
        self.use_signer = use_signer
        self.permanent = permanent
        self.has_same_site_capability = hasattr(self, "get_cookie_samesite")
        if self.use_signer:
            self.signer = Signer(secret_key, salt='flask-session',
                                 key_derivation='hmac')

    def open_session(self, app, request):
        """
        This method opens a session for the user by retrieving the session data from Redis.
        If no session ID (SID) is found in the cookies, it generates a new one.
        If session data is available in Redis, it loads the session; otherwise, it creates a new session.

        :param app: The Flask application instance.
        :param request: The Flask request object.
        :return: The user session.
        """
        sid = request.cookies.get(app.config['SESSION_COOKIE_NAME'])
        if not sid:
            sid = self.generate_sid()
            # current_app.logger.debug(f"Generated new session ID: {sid}")
        # else:
            # current_app.logger.debug(f"Existing session ID: {sid}")

        max_retry_attempts = 3
        retry_attempts = 0

        while retry_attempts < max_retry_attempts:
            try:
                val = self.redis.get(self.key_prefix + sid)
                if val is not None:
                    data = self.serializer.loads(val)
                    session = self.session_class(initial=data, sid=sid)
                    # Ensure '_id' matches 'sid'
                    session['_id'] = sid
                    # current_app.logger.debug(f"Loaded session data: {dict(session)}")
                    return session
                break  # Exit loop if there is no value
            except Exception as e:
                retry_attempts += 1
                current_app.logger.warning(f"Attempt {retry_attempts}: Failed to load session data for SID: {sid}, Error: {e}")
                if retry_attempts >= max_retry_attempts:
                    raise e

        # Create new session
        session = self.session_class(sid=sid, permanent=self.permanent)
        session['_id'] = sid
        # current_app.logger.debug(f"Created new session: {dict(session)}")
        return session

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            if session.modified:
                self.redis.delete(self.key_prefix + session.sid)
                response.delete_cookie(app.config['SESSION_COOKIE_NAME'],
                                       domain=domain, path=path)
            return

        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        expires = self.get_expiration_time(app, session)

        session['_id'] = session.sid
        val = self.serializer.dumps(dict(session))

        max_age = int(app.permanent_session_lifetime.total_seconds())
        self.redis.setex(name=self.key_prefix + session.sid, value=val,
                         time=max_age)

        if self.use_signer:
            session_id = self.signer.sign(want_bytes(session.sid))
        else:
            session_id = session.sid
        #current_app.logger.debug(f"Saving session with ID: {session.sid}")

        response.set_cookie(app.config['SESSION_COOKIE_NAME'], session_id,
                            expires=expires, httponly=httponly,
                            domain=domain, path=path, secure=secure)

    def generate_sid(self):
        new_sid = str(uuid.uuid4())
        #current_app.logger.debug(f"Generated new session ID: {new_sid}")
        return new_sid

def is_mobile():
    user_agent_string = request.headers.get('User-Agent')
    user_agent = parse(user_agent_string)
    return user_agent.is_mobile

## Create the app object
## This function is called when the app is created.

def create_app(secret_key=None, instance_id=None):
    app = Flask(__name__, static_folder='static')

    app.config['WIX_API_KEY'] = get_secret('WIX-API-KEY')
    app.config['WIX_SITE_ID'] = get_secret('WIX-SITE-ID')

    wix_db = WixDatabase(api_key=app.config['WIX_API_KEY'], site_id=app.config['WIX_SITE_ID'])
    wix_db.init_app(app)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    origins=[
        "http://localhost",
        "https://localhost",
        "http://localhost:443",
        "https://localhost:443",
        "https://localhost:8000",
        "http://localhost:8000",
        "https://www.mindorah.com",
        "https://www.mindorah.com/demo",
        "https://mindorah.com",
        "https://editor.wix.com"
    ]

    # Clarified CORS configuration
    CORS(app, supports_credentials=True, resources={r"/*": {
        "origins": origins,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
        "expose_headers": ["Content-Type", "Authorization"],
        "max_age": 600
    }})

    app.config['SECRET_KEY'] = secret_key or 'AseOlgTpPTsz46P'
    app.config['INSTANCE_ID'] = instance_id
    app.config['SESSION_COOKIE_NAME'] = 'session'
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'https'

    # Redis configuration
    host = "mindorah-interviewer-redis.redis.cache.windows.net"
    port = 6380
    password = get_secret('KEY1-REDIS')

    try:
        # Create a retry strategy with exponential backoff
        retry_strategy = Retry(
            retries=3,
            backoff=ExponentialBackoff(cap=1, base=0.1)  # Start with 0.1s, increase exponentially, cap at 1s
        )

        # Create Redis client with retry strategy
        redis_client = redis.Redis(
            host=host,
            port=port,
            password=password,
            ssl=True,
            decode_responses=True,
            socket_keepalive=True,
            socket_timeout=300,
            retry=retry_strategy,
            retry_on_timeout=True
        )

        redis_client.ping()  # Test the connection
        app.logger.info("Successfully connected to Azure Redis Cache")
    except Exception as e:
        app.logger.error(f"Error connecting to Redis: {e}")
        raise

    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = redis_client
    app.config['SESSION_KEY_PREFIX'] = f'session:{instance_id}:'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

    # Use custom SessionInterface
    app.session_interface = InstanceAwareRedisSessionInterface(
        redis=redis_client,
        key_prefix=app.config['SESSION_KEY_PREFIX'],
        secret_key=app.config['SECRET_KEY'],
        use_signer=app.config.get('SESSION_USE_SIGNER', False),
        permanent=app.config.get('SESSION_PERMANENT', False)
    )

    configure_logging(app)
    # Import webApp routes...
    from .candidate_view import candidate_view
    from .candidate_auth import candidate_auth
    from .server import server
    from .secrets import secrets
    # Register blueprints...
    app.register_blueprint(candidate_view, url_prefix="/candidate")
    app.register_blueprint(candidate_auth, url_prefix="/candidate")
    app.register_blueprint(server, url_prefix="/server")
    app.register_blueprint(secrets, url_prefix="/secrets")
    app.register_blueprint(animation_bp)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'  # Set your login view

    @login_manager.user_loader
    def load_user(item_id):
        user_data = session.get('user_data')
        if user_data and str(user_data.get('item_id')) == str(item_id):
            return User(**user_data)  # Now this will work because User accepts all these parameters

        current_app.logger.error(f"User {item_id} not found in session.")
        return None

    @app.route('/')
    def home():
        return render_template('error.html')

    @app.route('/favicon.ico')
    def favicon():
        try:
            return send_from_directory(os.path.join(app.root_path, 'static', 'assets', 'images', 'favicons'),
                                    'favicon.ico', mimetype='image/vnd.microsoft.icon')
        except Exception as e:
            app.logger.error(f"Error serving favicon: {str(e)}")
            return '', 404  # Return a 404 if the favicon can't be served

    @app.route('/mobile')
    def mobile_message():
        return render_template('mobile.html')

    @app.before_request
    def before_request():
        try:
            # Check if we are on a mobile device.
            #if is_mobile() and request.endpoint not in ['mobile_message', 'static']:
            #    return redirect(url_for('mobile_message'))

            # Set session param, check if there's any problems with the session
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=1)

            if '_id' not in session or session['_id'] != session.sid:
                current_app.logger.warning(f"Session inconsistency detected. _id: {session.get('_id')}, sid: {session.sid}")
                session['_id'] = session.sid
                session.modified = True
        except Exception as e:
            current_app.logger.error(f"Error in before_request: {str(e)}")

    @app.after_request
    def after_request(response):
        try:
            # Set Content Security Policy header
            response.headers['Content-Security-Policy'] = "frame-ancestors *"

        except Exception as e:
            current_app.logger.error(f"Error in after_request: {str(e)}")

        return response

    return app

def configure_logging(app):
    import colorlog

    LOGGING_LEVEL = logging.WARNING

    # Ensure the logs directory exists
    logs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(logs_path):
        os.makedirs(logs_path)

    log_colors = {
        'DEBUG': 'reset',
        'INFO': 'reset',
        'WARNING': 'bold_yellow',
        'ERROR': 'bold_red',
        'CRITICAL': 'bold_red,bg_white',
    }

    class CustomFormatter(colorlog.ColoredFormatter):
        def format(self, record):
            # Add relative file path and line number to the record
            record.custom_filename = os.path.basename(record.pathname)
            record.custom_lineno = record.lineno
            return super().format(record)

    # Create a color formatter for the console handler
    color_formatter = CustomFormatter(
        '%(blue)s%(asctime)s%(reset)s %(log_color)s%(levelname)s:%(reset)s %(message)s [in %(custom_filename)s:%(custom_lineno)d]',
        datefmt='%Y-%m-%d %H:%M:%S',
        reset=True,
        log_colors=log_colors
    )

    # Remove all existing handlers from the app.logger to avoid duplication
    app.logger.handlers.clear()

    # Create a file handler
    file_handler = RotatingFileHandler(os.path.join(logs_path, f'app_{app.config["INSTANCE_ID"]}.log'), maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    file_handler.setLevel(LOGGING_LEVEL)
    app.logger.addHandler(file_handler)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(color_formatter)
    console_handler.setLevel(LOGGING_LEVEL)
    app.logger.addHandler(console_handler)

    # Set the root logger level
    logging.getLogger().setLevel(LOGGING_LEVEL)
    app.logger.setLevel(LOGGING_LEVEL)
