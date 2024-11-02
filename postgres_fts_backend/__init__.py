"""
A ORM-based backend for Postgres FTS search \.
"""

from warnings import warn

from django.contrib.postgres.search import SearchQuery
from django.db.models import Q
from haystack import connections
from haystack.backends import (
    BaseEngine,
    BaseSearchBackend,
    BaseSearchQuery,
    SearchNode,
    log_query,
)
from haystack.constants import DEFAULT_ALIAS
from haystack.inputs import Clean, PythonData
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
    def search(self, orm_query, **kwargs):
        hits = 0
        results = []
        result_class = SearchResult
        try:
            (model,) = (
                connections[self.connection_alias]
                .get_unified_index()
                .get_indexed_models()
            )
        except ValueError:
            raise NotImplementedError(
                "The Postgres FTS backend does not currently searching across"
                "more than one model"
            )

        if kwargs.get("result_class"):
            result_class = kwargs["result_class"]

        if kwargs.get("models"):
            (model,) = kwargs["models"]

        qs = model.objects.filter(orm_query)

        hits += len(qs)

        for match in qs:
            match.__dict__.pop("score", None)
            app_label, model_name = get_model_ct_tuple(match)
            result = result_class(app_label, model_name, match.pk, 0, **match.__dict__)
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

        if not hasattr(value, "input_type_name"):
            # Handle when we've got a ``ValuesListQuerySet``...
            if hasattr(value, "values_list"):
                value = list(value)

            if isinstance(value, str):
                # It's not an ``InputType``. Assume ``Clean``.
                value = Clean(value)
            else:
                value = PythonData(value)

        prepared_value = value.prepare(self)

        unified_index = connections[self._using].get_unified_index()

        if field == "content":
            model_field = unified_index.fields[unified_index.document_field].model_attr
        else:
            try:
                model_field = unified_index.fields[field].model_attr
            except KeyError:
                raise ValueError(f"{field} is not an indexed field.")

        if filter_type == "content":
            search_string = SearchQuery(prepared_value, search_type="websearch")
        else:
            search_string = prepared_value

        return Q(**{f"{model_field}__search": search_string})

    def build_query(self):
        """
        Interprets the collected query metadata and builds the final query to
        be sent to the backend.
        """
        unified_index = connections[self._using].get_unified_index()

        if len(unified_index.indexes) > 1:
            raise NotImplementedError(
                "The Postgres FTS backend does not currently searching across"
                "more than one model"
            )

        final_query = self.query_filter.as_orm_query(self.build_query_fragment)

        if not final_query:
            # Match all.
            final_query = self.matching_all_fragment()

        if self.boost:
            boost_list = []

            for boost_word, boost_value in self.boost.items():
                boost_list.append(self.boost_fragment(boost_word, boost_value))

            final_query = "%s %s" % (final_query, " ".join(boost_list))

        return final_query

    def matching_all_fragment(self):

        return Q()

    def build_not_query(self, query_string):
        if " " in query_string:
            query_string = "(%s)" % query_string

        return "-%s" % query_string


class PostgresSearchNode(SearchNode):

    def as_orm_query(self, query_fragment_callback):
        result = []

        for child in self.children:
            if hasattr(child, "as_orm_query"):
                result.append(child.as_orm_query(query_fragment_callback))
            else:
                expression, value = child
                field, filter_type = self.split_expression(expression)
                result.append(query_fragment_callback(field, filter_type, value))

        query = Q()
        if self.connector == self.AND:
            for subquery in result:
                query &= subquery
        elif self.connector == self.OR:
            for subquery in result:
                query |= subquery

        if query:
            if self.negated:
                query = ~query

        return query


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
