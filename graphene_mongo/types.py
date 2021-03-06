from collections import OrderedDict

from graphene import Field, ObjectType
from graphene.relay import Connection, Node
from graphene.types.objecttype import ObjectType, ObjectTypeOptions
from graphene.types.utils import yank_fields_from_attrs

from .converter import convert_mongoengine_field
from .registry import Registry, get_global_registry
from .utils import (get_model_fields, is_valid_mongoengine_model)


def construct_fields(model, registry, only_fields, exclude_fields):
    _model_fields = get_model_fields(model)
    fields = OrderedDict()
    for name, field in _model_fields.items():
        is_not_in_only = only_fields and name not in only_fields
        is_excluded = name in exclude_fields
        if is_not_in_only or is_excluded:
            # We skip this field if we specify only_fields and is not
            # in there. Or when we exclude this field in exclude_fields
            continue
        converted = convert_mongoengine_field(field, registry)
        if not converted:
            continue
        fields[name] = converted

    return fields


class MongoengineObjectTypeOptions(ObjectTypeOptions):

    model = None  # type: Model
    registry = None  # type: Registry
    connection = None  # type: Type[Connection]
    filter_fields = ()

class MongoengineObjectType(ObjectType):

    @classmethod
    def __init_subclass_with_meta__(cls, model=None, registry=None, skip_registry=False,
                                    only_fields=(), exclude_fields=(), filter_fields=None, connection=None,
                                    connection_class=None, use_connection=None, interfaces=(), **options):

        assert is_valid_mongoengine_model(model), (
            'You need to pass a valid Mongoengine Model in {}.Meta, received "{}".'
        ).format(cls.__name__, model)

        if not registry:
            registry = get_global_registry()

        assert isinstance(registry, Registry), (
            'The attribute registry in {} needs to be an instance of '
            'Registry, received "{}".'
        ).format(cls.__name__, registry)

        mongoengine_fields = yank_fields_from_attrs(
            construct_fields(model, registry, only_fields, exclude_fields),
            _as=Field
        )
        if use_connection is None and interfaces:
            use_connection = any((issubclass(interface, Node) for interface in interfaces))

        if use_connection and not connection:
            # We create the connection automatically
            if not connection_class:
                connection_class = Connection

            connection = connection_class.create_type(
                '{}Connection'.format(cls.__name__), node=cls)

        if connection is not None:
            assert issubclass(connection, Connection), (
                'The connection must be a Connection. Received {}'
            ).format(connection.__name__)

        _meta = MongoengineObjectTypeOptions(cls)
        _meta.model = model
        _meta.registry = registry
        _meta.fields = mongoengine_fields
        _meta.filter_fields = filter_fields
        _meta.connection = connection
        super(MongoengineObjectType, cls).__init_subclass_with_meta__(
            _meta=_meta, interfaces=interfaces, **options
        )

        if not skip_registry:
            registry.register(cls)

    @classmethod
    def is_type_of(cls, root, info):
        if isinstance(root, cls):
            return True
        if not is_valid_mongoengine_model(type(root)):
            raise Exception((
                'Received incompatible instance "{}".'
            ).format(root))
        return isinstance(root, cls._meta.model)

    @classmethod
    def get_node(cls, id, context, info):
        if isinstance(getattr(cls._meta.model, get_key_name(cls._meta.model)), NumberAttribute):
            return cls._meta.model.get(int(id))

        return cls._meta.model.get(id)

    def resolve_id(self, info):
        return str(self.id)

    #@classmethod
    #def get_connection(cls):
    #    return connection_for_type(cls)

