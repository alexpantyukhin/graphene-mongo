import json

import graphene

from graphene.relay import Node

from .models import Article, Editor, EmbeddedArticle, Reporter
from .utils import with_local_registry
from ..fields import MongoengineConnectionField
from ..types import MongoengineObjectType


def setup_fixtures():
    editor1 = Editor(first_name='Penny', last_name='Hardaway')
    editor1.save()
    editor2 = Editor(first_name='Grant', last_name='Hill')
    editor2.save()

    reporter = Reporter(first_name='Allen', last_name='Iverson',
                        email='ai@gmail.com',  awards=['2010-mvp'])
    article1 = Article(headline='Hello', editor=editor1)
    article1.save()
    article2 = Article(headline='World', editor=editor2)
    article2.save()
    reporter.articles = [article1, article2]
    reporter.save()

setup_fixtures()


@with_local_registry
def test_should_query_editor_well():
    class EditorType(MongoengineObjectType):
        class Meta:
            model = Editor

    class Query(graphene.ObjectType):
       editor = graphene.Field(EditorType)
       editors = graphene.List(EditorType)

       def resolve_editor(self, *args, **kwargs):
           return Editor.objects.first()

       def resolve_editors(self, *args, **kwargs):
           return list(Editor.objects.all())

    query = '''
        query EditorQuery {
            editor {
                firstName
            }
            editors {
                firstName,
                lastName
            }
        }
    '''
    expected = {
        'editor': {
            'firstName': 'Penny'
        },
        'editors': [{
            'firstName': 'Penny',
            'lastName': 'Hardaway'
        }, {
            'firstName': 'Grant',
            'lastName': 'Hill'
        }]
        }

    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert dict(result.data['editor']) == expected['editor']
    assert all(item in result.data['editors'] for item in expected['editors'])


@with_local_registry
def test_should_query_reporter_well():
    class ArticleType(MongoengineObjectType):
        class Meta:
            model = Article

    class ReporterType(MongoengineObjectType):
        class Meta:
            model = Reporter

    class Query(graphene.ObjectType):
        reporter = graphene.Field(ReporterType)

        def resolve_reporter(self, *args, **kwargs):
            return Reporter.objects.first()

    query = '''
        query ReporterQuery {
            reporter {
                firstName,
                lastName,
                email,
                articles {
                    headline
                },
                awards
            }
        }
    '''
    expected = {
        'reporter': {
            'firstName': 'Allen',
            'lastName': 'Iverson',
            'email': 'ai@gmail.com',
            'articles': [
                {'headline': 'Hello'},
                {'headline': 'World'}
            ],
            'awards': ['2010-mvp']
        }
    }

    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert dict(result.data['reporter']) == expected['reporter']


@with_local_registry
def test_should_node():
    class ArticleNode(MongoengineObjectType):

        class Meta:
            model = Article
            interfaces = (Node,)

    class ReporterNode(MongoengineObjectType):

        class Meta:
            model = Reporter
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        reporter = graphene.Field(ReporterNode)

        def resolve_reporter(self, *args, **kwargs):
            return Reporter.objects.first()

    query = '''
        query ReporterQuery {
            reporter {
                firstName,
                articles {
                    edges {
                        node {
                            headline
                        }
                    }
                }
                lastName,
                email
            }
        }
    '''
    expected = {
        'reporter': {
            'firstName': 'Allen',
            'lastName': 'Iverson',
            'articles': {
                'edges': [
                    {
                        'node': {
                            'headline': 'Hello'
                        }
                    },
                    {
                        'node': {
                            'headline': 'World'
                        }
                    }
                ],
            },
            'email': 'ai@gmail.com'
        }
    }

    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert dict(result.data['reporter']) == expected['reporter']


@with_local_registry
def test_should_connection_field():
    class EditorNode(MongoengineObjectType):

        class Meta:
            model = Editor
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        all_editors = MongoengineConnectionField(EditorNode)

    query = '''
        query EditorQuery {
          allEditors {
            edges {
                node {
                    firstName,
                    lastName
                }
            }
          }
        }
    '''
    expected = {
        'allEditors': {
            'edges': [
                {
                    'node': {
                        'firstName': 'Penny',
                        'lastName': 'Hardaway'
                    },
                },
                {
                    'node': {
                        'firstName': 'Grant',
                        'lastName': 'Hill'
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert dict(result.data['allEditors']) == expected['allEditors']


@with_local_registry
def test_should_mutate_well():
    class ArticleNode(MongoengineObjectType):

        class Meta:
            model = Article
            interfaces = (Node,)


    class CreateArticle(graphene.Mutation):

        class Arguments:
            headline = graphene.String()

        article = graphene.Field(ArticleNode)

        def mutate(self, info, headline):
            article = Article(
                headline=headline
            )
            article.save()

            return CreateArticle(article=article)


    class Query(graphene.ObjectType):
        node = Node.Field()


    class Mutation(graphene.ObjectType):

        create_article = CreateArticle.Field()

    query = '''
        mutation ArticleCreator {
            createArticle(
                headline: "My Article"
            ) {
                article {
                    headline
                }
            }
        }
    '''
    expected = {
        'createArticle': {
            'article': {
                'headline': 'My Article'
            }
        }
    }
    schema = graphene.Schema(query=Query, mutation=Mutation)
    result = schema.execute(query)
    assert not result.errors
    assert result.data == expected

@with_local_registry
def test_should_filter():
    class ArticleNode(MongoengineObjectType):

        class Meta:
            model = Article
            interfaces = (Node,)
            filter_fields = ('headline',)

    class Query(graphene.ObjectType):
        node = Node.Field()
        articles = MongoengineConnectionField(ArticleNode)

    query = '''
        query ArticleQuery {
          articles(headline: "World") {
            edges {
                node {
                    headline
                }
            }
          }
        }
    '''
    expected = {
        'articles': {
            'edges': [
                {
                    'node': {
                        'headline': 'World'
                    }
                }
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert result.data == expected


# TODO:
def test_should_paging():
    pass

