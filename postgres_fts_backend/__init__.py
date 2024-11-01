"""
A ORM-based backend for Postgres FTS search \.
"""

from functools import reduce
from warnings import warn

from django.db.models import Q
from haystack import connections
from haystack.backends import (BaseEngine, BaseSearchBackend, BaseSearchQuery,
                               SearchNode, log_query)
from haystack.inputs import PythonData, Clean
from haystack.models import SearchResult
from haystack.utils import get_model_ct_tuple
from haystack.constants import DEFAULT_ALIAS


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
            print(query)
            
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

    def __init__(self, using=DEFAULT_ALIAS):
        super().__init__(using)
        self.query_filter = PostgresSearchNode()

    def build_query_fragment(self, field, filter_type, value):
        #if field == "content":
        #    index_fieldname = ""

        value_old = value
        #breakpoint()
        #
        if isinstance(value, str):
            # It's not an ``InputType``. Assume ``Clean``.
            value = Clean(value)
        else:
            value = PythonData(value)

        tokens = value.query_string.split()
        postgres_search_string = ' | '.join(tokens)

        return postgres_search_string



    def build_query(self):

        final_query = super().build_query()
        if '|' in final_query:
            breakpoint()

        return final_query


class PostgresSearchNode(SearchNode):

    def as_query_string(self, query_fragment_callback):
        """
        Produces a portion of the search query from the current SQ and its
        children.
        """
        result = []

        for child in self.children:
            if hasattr(child, "as_query_string"):
                result.append(child.as_query_string(query_fragment_callback))
            else:
                expression, value = child
                field, filter_type = self.split_expression(expression)
                result.append(query_fragment_callback(field, filter_type, value))

        conn = " & "
        query_string = conn.join(result)

        if query_string:
            if self.negated:
                query_string = "NOT (%s)" % query_string
            elif len(self.children) != 1:
                query_string = "(%s)" % query_string

        return query_string




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
                query = Q(pk__in=[])
            elif (py_value == "*" and not negated) or (py_value == "" and negated):
                pass
            elif field == "content":
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

                if negated:
                    query &= ~or_queries
                else:
                    query &= or_queries
            else:
                if negated:
                    query &= ~Q(**{f"{field}__search": py_value})
                else:
                    query &= Q(**{f"{field}__search": py_value})

    

    return query
