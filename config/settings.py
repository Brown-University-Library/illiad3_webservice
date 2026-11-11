import json
import os
from pathlib import Path

from dotenv import load_dotenv

"""
Django settings for the ILLiad webservice.
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parent.parent)
load_dotenv(Path(BASE_DIR).parent / '.env', override=True, interpolate=False)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['ILLIAD_WS__SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
temp_DEBUG = json.loads( os.environ['ILLIAD_WS__DEBUG_JSON'] )
assert temp_DEBUG in [ True, False ], Exception( 'DEBUG env setting is, "%s"' )
DEBUG = temp_DEBUG

ADMINS = json.loads( os.environ['ILLIAD_WS__ADMINS_JSON'] )

ALLOWED_HOSTS = json.loads( os.environ['ILLIAD_WS__ALLOWED_HOSTS'] )  # list


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'illiad_app',
)

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Existing API callers authenticate without browser CSRF tokens.
    # Keep this API's middleware behavior; no admin URL is exposed.
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'illiad_app.middleware.FormEncodingMiddleware',
)

# Preserve Django 1.11's framing and trailing-slash behavior for existing callers.
X_FRAME_OPTIONS = 'SAMEORIGIN'
APPEND_SLASH = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

ROOT_URLCONF = 'config.urls'

WSGI_APPLICATION = 'config.passenger_wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.environ['ILLIAD_WS__DATABASES_ENGINE'],
        'NAME': os.environ['ILLIAD_WS__DATABASES_NAME'],
        'USER': os.environ['ILLIAD_WS__DATABASES_USER'],
        'PASSWORD': os.environ['ILLIAD_WS__DATABASES_PASSWORD'],
        'HOST': os.environ['ILLIAD_WS__DATABASES_HOST'],
        'PORT': os.environ['ILLIAD_WS__DATABASES_PORT'],
    }
}


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = os.environ['ILLIAD_WS__STATIC_URL']
STATIC_ROOT = os.environ['ILLIAD_WS__STATIC_ROOT']  # needed for collectstatic command


# Templates

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': json.loads(os.environ['ILLIAD_WS__TEMPLATE_DIRS']),
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# Email
SERVER_EMAIL = os.environ['ILLIAD_WS__SERVER_EMAIL']
EMAIL_HOST = os.environ['ILLIAD_WS__EMAIL_HOST']
EMAIL_PORT = int( os.environ['ILLIAD_WS__EMAIL_PORT'] )


# sessions

# <https://docs.djangoproject.com/en/5.2/ref/settings/#std:setting-SESSION_SAVE_EVERY_REQUEST>
# Thinking: not that many concurrent users, and no pages where session info isn't required, so overhead is reasonable.
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s",
            'datefmt': "%d/%b/%Y %H:%M:%S"
        },
    },
    'handlers': {
        'logfile': {
            'level':'DEBUG',
            'class':'logging.FileHandler',  # note: configure server to use system's log-rotate to avoid permissions issues
            'filename': os.environ.get('ILLIAD_WS__LOG_PATH'),
            'formatter': 'standard',
        },
        'console':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'standard'
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'illiad_app': {
            'handlers': ['logfile'],
            'level': os.environ.get('ILLIAD_WS__LOG_LEVEL'),
            'propagate': False
        },
    }
}

