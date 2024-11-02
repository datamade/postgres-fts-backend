from django.contrib.postgres.search import SearchQuery
from django.db.models import Q
from django.test import TestCase
from haystack import connections
from haystack.models import SearchResult
from haystack.query import SQ

from .search_indexes import SimpleMockSearchIndex


class SimpleSearchQueryTestCase(TestCase):
    def setUp(self):
        super().setUp()

        ui = connections["default"].get_unified_index()
        ui.build(indexes=[SimpleMockSearchIndex()])

        self.sq = connections["default"].get_query()

    def test_build_query_all(self):
        self.assertEqual(self.sq.build_query(), Q())

    def test_build_query_single_word(self):
        self.sq.add_filter(SQ(content="hello"))
        self.assertEqual(
            self.sq.build_query(),
            Q(foo__search=SearchQuery("hello", search_type="websearch")),
        )

    def test_build_query_multiple_word(self):
        self.sq.add_filter(SQ(name="foo"))
        self.sq.add_filter(SQ(name="bar"))
        self.assertEqual(
            self.sq.build_query(),
            Q(author__search=SearchQuery("foo", search_type="websearch"))
            & Q(author__search=SearchQuery("bar", search_type="websearch")),
        )

    def test_build_query_or(self):
        self.sq.add_filter(SQ(name="foo"))
        self.sq.add_filter(SQ(name="bar"), use_or=True)
        self.assertEqual(
            self.sq.build_query(),
            Q(author__search=SearchQuery("foo", search_type="websearch"))
            | Q(author__search=SearchQuery("bar", search_type="websearch")),
        )

    def test_set_result_class(self):
        # Assert that we're defaulting to ``SearchResult``.
        self.assertTrue(issubclass(self.sq.result_class, SearchResult))

        # Custom class.
        class IttyBittyResult:
            pass

        self.sq.set_result_class(IttyBittyResult)
        self.assertTrue(issubclass(self.sq.result_class, IttyBittyResult))

        # Reset to default.
        self.sq.set_result_class(None)
        self.assertTrue(issubclass(self.sq.result_class, SearchResult))
