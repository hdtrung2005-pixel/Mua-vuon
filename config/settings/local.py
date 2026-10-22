"""Settings cho môi trường local/dev."""
from .base import *  # noqa

DEBUG = True

# Cho phép browsable API + debug toolbar sau này nếu cần
CORS_ALLOW_ALL_ORIGINS = True
