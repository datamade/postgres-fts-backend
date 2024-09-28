# Haystack settings for running tests.
DATABASES = {
    "default": {"ENGINE": "django.db.backends.postgresql", "NAME": "haystack_tests"}
}

# Use BigAutoField as the default auto field for all models
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.postgres",
    "haystack",
    "tests.core",
]

HAYSTACK_CONNECTIONS = {
    "default": {"ENGINE": "postgres_fts_backend.PostgresFTSEngine"},
}
