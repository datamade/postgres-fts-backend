# Haystack settings for running tests.
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "haystack_tests.db"}
}

# Use BigAutoField as the default auto field for all models
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "haystack",
    "tests.core",
]

HAYSTACK_CONNECTIONS = {
    "default": {"ENGINE": "postgres_fts_backend.PostgresFTSEngine"},
}
