from haystack import indexes

from tests.core.models import MockModel, ScoreMockModel, UUIDMockModel


class SimpleMockSearchIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr="foo")
    name = indexes.CharField(model_attr="author")
    pub_date = indexes.DateTimeField(model_attr="pub_date")

    def get_model(self):
        return MockModel


class SimpleMockScoreIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr="score")
    score = indexes.CharField(model_attr="score")

    def get_model(self):
        return ScoreMockModel


class SimpleMockUUIDModelIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, model_attr="characteristics")

    def get_model(self):
        return UUIDMockModel
