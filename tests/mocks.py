from django.apps import apps
from haystack.models import SearchResult


class MockSearchResult(SearchResult):
    def __init__(self, app_label, model_name, pk, score, **kwargs):
        super().__init__(app_label, model_name, pk, score, **kwargs)
        self._model = apps.get_model("core", model_name)
