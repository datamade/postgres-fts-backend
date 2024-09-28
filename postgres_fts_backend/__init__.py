"""
A ORM-based backend for Postgres FTS search \.
"""

from functools import reduce
from warnings import warn

from django.db.models import Q
from haystack import connections
from haystack.backends import (BaseEngine, BaseSearchBackend, BaseSearchQuery,
                               SearchNode, log_query)
from haystack.inputs import PythonData
from haystack.models import SearchResult
from haystack.utils import get_model_ct_tuple


class PostgresFTSSearchBackend(BaseSearchBackend):
    def update(self, indexer, iterable, commit=True):
        warn("update is not implemented in this backend")

    def remove(self, obj, commit=True):
        warn("remove is not implemented in this backend")

    def clear(self, models=None, commit=True):
        warn("clear is not implemented in this backend")

    @log_query
    def search(self, query_filter, **kwargs):
        hits = 0
        results = []
        result_class = SearchResult
        models = (
            connections[self.connection_alias].get_unified_index().get_indexed_models()
        )

        if kwargs.get("result_class"):
            result_class = kwargs["result_class"]

        if kwargs.get("models"):
            models = kwargs["models"]

        for model in models:
            query = build_query(model, query_filter)
            qs = model.objects.filter(query)

            hits += len(qs)

            for match in qs:
                match.__dict__.pop("score", None)
                app_label, model_name = get_model_ct_tuple(match)
                result = result_class(
                    app_label, model_name, match.pk, 0, **match.__dict__
                )
                # For efficiency.
                result._model = match.__class__
                result._object = match
                results.append(result)

        return {"results": results, "hits": hits}

    def prep_value(self, db_field, value):
        return value

    def more_like_this(
        self,
        model_instance,
        additional_query_string=None,
        start_offset=0,
        end_offset=None,
        limit_to_registered_models=None,
        result_class=None,
        **kwargs,
    ):
        return {"results": [], "hits": 0}


class PostgresFTSSearchQuery(BaseSearchQuery):

    def build_query(self):
        print(self.query_filter)
        return self.query_filter


class PostgresFTSEngine(BaseEngine):
    backend = PostgresFTSSearchBackend
    query = PostgresFTSSearchQuery


def build_query(model, search_node, negated=False):
    print(search_node)

    query = Q()

    for child in search_node.children:
        if isinstance(child, SearchNode):
            if child.connector == "AND":
                query &= build_query(model, child, child.negated)
            elif child.connector == "OR":
                query |= build_query(model, child, child.negated)
            else:
                breakpoint()
        else:
            expression, value = child
            field, filter_type = search_node.split_expression(expression)

            py_value = str(value)

            if (py_value == "" and not negated) or (py_value == "*" and negated):
                query = Q(pk_in=[])
            elif field == "content":
                if negated:
                    if py_value == "":
                        pass
                    else:
                        or_queries = Q()
                        for model_field in model._meta.fields:
                            if hasattr(field, "related"):
                                continue

                            if model_field.get_internal_type() not in (
                                "TextField",
                                "CharField",
                                "SlugField",
                            ):
                                continue

                            or_queries |= Q(**{f"{model_field.name}__search": py_value})
                        query &= ~or_queries
                else:
                    if py_value == "*":
                        pass
                    else:
                        or_queries = Q()
                        for model_field in model._meta.fields:
                            if hasattr(field, "related"):
                                continue

                            if model_field.get_internal_type() not in (
                                "TextField",
                                "CharField",
                                "SlugField",
                            ):
                                continue

                            or_queries |= Q(**{f"{model_field.name}__search": py_value})
                        query &= or_queries
            else:
                if negated:
                    if py_value == "":
                        pass
                    else:
                        query &= ~Q(**{f"{field}__search": py_value})
                else:
                    if py_value == "*":
                        pass
                    else:
                        query &= Q(**{f"{field}__search": py_value})

    return query
