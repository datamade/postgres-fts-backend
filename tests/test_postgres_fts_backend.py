from datetime import date

from django.test import TestCase
from django.test.utils import override_settings
from haystack import connections
from haystack.query import SearchQuerySet
from haystack.utils.loading import UnifiedIndex

from tests.core.models import MockModel, OneToManyRightSideModel, ScoreMockModel

from .mocks import MockSearchResult
from .search_indexes import SimpleMockScoreIndex, SimpleMockSearchIndex


class SimpleSearchBackendTestCase(TestCase):
    fixtures = ["base_data.json", "bulk_data.json"]

    def setUp(self):
        super().setUp()

        self.backend = connections["default"].get_backend()
        ui = connections["default"].get_unified_index()
        self.index = SimpleMockSearchIndex()
        ui.build(indexes=[self.index, SimpleMockScoreIndex()])
        self.sample_objs = MockModel.objects.all()

        self.sqs = SearchQuerySet(using="default")

    def test_update(self):
        self.backend.update(self.index, self.sample_objs)

    def test_remove(self):
        self.backend.remove(self.sample_objs[0])

    def test_clear(self):
        self.backend.clear()

    def test_search(self):
        # No query string should always yield zero results.
        self.assertEqual(self.backend.search(self.sqs.auto_query("").query.query_filter), {"hits": 0, "results": []})

        self.assertEqual(
            sorted(
                [
                    result.pk
                    for result in self.backend.search(
                        self.sqs.auto_query("*").query.query_filter
                    )["results"]
                ]
            ),
            [
                1,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
            ],
        )

        self.assertEqual(self.backend.search(self.sqs.auto_query("daniel1").query.query_filter)["hits"], 7)
        self.assertEqual(
            [result.pk for result in self.backend.search(self.sqs.auto_query("daniel1").query.query_filter)["results"]],
            [1, 5, 6, 7, 9, 11, 18]
        )

        self.assertEqual(self.backend.search(self.sqs.auto_query("should be a string").query.query_filter)["hits"], 1)
        self.assertEqual(
            [
                result.pk
                for result in self.backend.search(self.sqs.auto_query("should be a string").query.query_filter)["results"]
            ],
            [8],
        )
        # Ensure the results are ``SearchResult`` instances...
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("should be a string").query.query_filter)["results"][0].score, 0
        )

        self.assertEqual(self.backend.search(self.sqs.auto_query("index document").query.query_filter)["hits"], 6)
        self.assertEqual(
            [result.pk for result in self.backend.search(self.sqs.auto_query("index document").query.query_filter)["results"]],
            [2, 3, 15, 16, 17, 18],
        )

        # Regression-ville
        self.assertEqual(
            [
                result.object.id
                for result in self.backend.search(self.sqs.auto_query("index document").query.query_filter)["results"]
            ],
            [2, 3, 15, 16, 17, 18],
        )
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("index document").query.query_filter)["results"][0].model, MockModel
        )

        # No support for spelling suggestions
        self.assertEqual(self.backend.search(self.sqs.auto_query("Indx").query.query_filter)["hits"], 0)
        self.assertFalse(self.backend.search(self.sqs.auto_query("Indx").query.query_filter).get("spelling_suggestion"))

        # No support for facets
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("").query.query_filter, facets=["name"]), {"hits": 0, "results": []}
        )
        self.assertEqual(self.backend.search(self.sqs.auto_query("daniel1").query.query_filter, facets=["name"])["hits"], 7)
        self.assertEqual(
            self.backend.search(
                self.sqs.auto_query("").query.query_filter,
                date_facets={
                    "pub_date": {
                        "start_date": date(2008, 2, 26),
                        "end_date": date(2008, 2, 26),
                        "gap": "/MONTH",
                    }
                },
            ),
            {"hits": 0, "results": []},
        )
        self.assertEqual(
            self.backend.search(
                self.sqs.auto_query("daniel1").query.query_filter,
                date_facets={
                    "pub_date": {
                        "start_date": date(2008, 2, 26),
                        "end_date": date(2008, 2, 26),
                        "gap": "/MONTH",
                    }
                },
            )["hits"],
            7,
        )
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("").query.query_filter, query_facets={"name": "[* TO e]"}),
            {"hits": 0, "results": []},
        )
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("daniel1").query.query_filter, query_facets={"name": "[* TO e]"})["hits"], 7
        )
        self.assertFalse(self.backend.search(self.sqs.auto_query("").query.query_filter).get("facets"))
        self.assertFalse(self.backend.search(self.sqs.auto_query("daniel1").query.query_filter).get("facets"))

        # Note that only textual-fields are supported.
        self.assertEqual(self.backend.search(self.sqs.auto_query("2009-06-18").query.query_filter)["hits"], 0)

        # Ensure that swapping the ``result_class`` works.
        self.assertTrue(
            isinstance(
                self.backend.search(self.sqs.auto_query("index document").query.query_filter, result_class=MockSearchResult)[
                    "results"
                ][0],
                MockSearchResult,
            )
        )

        # Ensure empty queries does not raise.
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("foo").query.query_filter, models=[OneToManyRightSideModel]),
            {"hits": 0, "results": []},
        )

    def test_filter_models(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(
            self.backend.search(
                self.sqs.auto_query("*").query.query_filter, models=set([])
            )["hits"],
            24,
        )
        self.assertEqual(
            self.backend.search(
                self.sqs.auto_query("*").query.query_filter, models=set([MockModel])
            )["hits"],
            23,
        )

    def test_more_like_this(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(self.backend.search(self.sqs.auto_query("*").query.query_filter)["hits"], 24)

        # Unsupported by 'simple'. Should see empty results.
        self.assertEqual(self.backend.more_like_this(self.sample_objs[0])["hits"], 0)

    def test_score_field_collision(self):
        index = connections["default"].get_unified_index().get_index(ScoreMockModel)
        sample_objs = ScoreMockModel.objects.all()

        self.backend.update(index, self.sample_objs)

        # 42 is the in the match, which will be removed from the result
        self.assertEqual(
            self.backend.search(self.sqs.auto_query("42").query.query_filter)["results"][0].score, 0
        )


@override_settings(DEBUG=True)
class LiveSimpleSearchQuerySetTestCase(TestCase):
    fixtures = ["base_data.json", "bulk_data.json"]

    def setUp(self):
        super().setUp()

        # Stow.
        self.old_ui = connections["default"].get_unified_index()
        self.ui = UnifiedIndex()
        self.smmi = SimpleMockSearchIndex()
        self.ui.build(indexes=[self.smmi])
        connections["default"]._index = self.ui

        self.sample_objs = MockModel.objects.all()
        self.sqs = SearchQuerySet(using="default")

    def tearDown(self):
        # Restore.
        connections["default"]._index = self.old_ui
        super().tearDown()

    def test_general_queries(self):
        # For now, just make sure these don't throw an exception.
        # They won't work until the simple backend is improved.
        self.assertTrue(len(self.sqs.auto_query("daniel1")) > 0)
        self.assertTrue(len(self.sqs.filter(foo="index")) > 0)
        self.assertTrue(len(self.sqs.exclude(author="daniel1")) > 0)
        self.assertTrue(len(self.sqs.order_by("-pub_date")) > 0)

    def test_general_queries_unicode(self):
        self.assertEqual(len(self.sqs.auto_query("Привет")), 0)

    def test_more_like_this(self):
        # MLT shouldn't be horribly broken. This used to throw an exception.
        mm1 = MockModel.objects.get(pk=1)
        self.assertEqual(len(self.sqs.filter(text=1).more_like_this(mm1)), 0)

    def test_values_queries(self):
        sqs = self.sqs.auto_query("daniel1")
        self.assertTrue(len(sqs) > 0)

        flat_scores = sqs.values_list("score", flat=True)
        self.assertEqual(flat_scores[0], 0)

        scores = sqs.values_list("id", "score")
        self.assertEqual(scores[0], [1, 0])

        scores_dict = sqs.values("id", "score")
        self.assertEqual(scores_dict[0], {"id": 1, "score": 0})
