from __future__ import annotations

from datetime import datetime
from functools import cached_property
from inspect import getmembers, signature
from sys import version_info
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Dict, Generic, Iterator, List, Mapping, Optional, Tuple, Type, TypeVar, Union

from attr import AttrsInstance
from attrs import Attribute, define, field, fields
from cattrs import Converter, GenConverter

from tracs.uid import UID
from tracs.utils import fromisoformat, toisoformat

FIELD_KWARGS = {
	'init': True,
	'repr': True,
	'hash': True,
	'compare': True,
}

FIELD_KWARGS = FIELD_KWARGS if version_info.minor < 10 else { **FIELD_KWARGS, 'kw_only': False }

T = TypeVar('T')

@define
class Container( Generic[T] ):
	"""
	Dict-like container for activities/resources and the like. Super class to put common methods into.
	"""

	data: List[T] = field( factory=list )

	__id_map__: Dict[int, T] = field( factory=dict, init=False, alias='__id_map__' )
	__uid_map__: Dict[str, T] = field( factory=dict, init=False, alias='__uid_map__' )
	__it__: Iterator = field( default=None, init=False, alias='__it__' )

	# fill post init later
	def __attrs_post_init__( self ):
		pass

	# calculation of next id
	def __next_id__( self ) -> int:
		existing_ids = [r.id for r in self.data]
		id_range = range( 1, max( existing_ids ) + 2 ) if len( existing_ids ) > 0 else [1]
		return set( id_range ).difference( set( existing_ids ) ).pop()

	# len() support

	def __len__( self ) -> int:
		return len( self.data )

	# iteration support

	def __iter__( self ):
		self.__it__ = self.data.__iter__()
		return self.__it__

	def __next__( self ):
		return self.__it__.__next__()

	# dict-like access

	# this might be overridden in subclasses
	def __contains__( self, item: T ) -> bool:
		try:
			return any( [item.uid == r.uid for r in self.data] )
		except AttributeError:
			return False

	def __getitem__( self, key: str ):
		return self.__uid_map__[key]

	# various helpers

	def get( self, key: str ) -> Optional[T]:
		return next( (i for i in self.data if i.uid == key ), None )

	def idget( self, key: int ) -> Optional[T]:
		return next( (i for i in self.data if i.id == key ), None )

	def ids( self ) -> List[int]:
		return [r.id for r in self.data]

	def keys( self ) -> List[str]:
		return list( self.__uid_map__.keys() )

	def values( self ) -> List[T]:
		return list( self.data )

	def items( self ) -> List[Tuple[str, T]]:
		return list( self.__uid_map__.items() )

	def uid_map( self ) -> Mapping[str, T]:
		return MappingProxyType( self.__uid_map__ )

	def uid_keys( self ) -> List[str]:
		return list( self.__uid_map__.keys() )

	def id_map( self ) -> Mapping[int, T]:
		return MappingProxyType( self.__id_map__ )

	def id_keys( self ) -> List[int]:
		return list( self.__id_map__.keys() )

	# content access

	def all( self, sort=False ) -> List[T]:
		# todo: we could also sort by id, not str( id )
		return list( self.data ) if not sort else sorted( self.data, key=lambda r: str( r.id ) )

	# content modification, check if this can be generalized

	def add( self, *items: Union[T, List[T]] ) -> List[int]:
		pass

	def update( self, *items: Union[T, List[T]] ) -> Tuple[List[int], List[int]]:
		pass

@define( init=False )
class Metadata:

	converter: ClassVar[Converter] = GenConverter( omit_if_default=True )

	created: Optional[datetime] = field( default=None )
	modified: Optional[datetime] = field( default=None )

	favourite: bool = field( default=False )

	# member: UID = field( default=None ) # indicator that an activity is a member of a group, not used yet
	members: List[UID] = field( default=[] ) # used for groups to indicate group members

	# part: List[UID] = field( factory=list ) # indicator that an activity is part of one or multiple others, not used yet
	# parts: List = field( factory=list ) # indicates parts of a multipart activity

	supplementary: Dict[str, Any] = field( factory=dict )
	# __kwargs__: Dict[str, Any] = field( factory=dict, alias='__kwargs__' )

	@cached_property
	def __fieldnames( self ) -> List[str]:
		return [f.name for f in fields( self.__class__ )]

	@cached_property
	def __regular_fieldnames( self ) -> List[str]:
		return [f.name for f in fields( self.__class__ ) if not f.name == 'supplementary']

	# noinspection PyUnresolvedReferences
	def __init__( self, *args, **kwargs ):
		self.__attrs_init__( *args, **{ k: v for k, v in kwargs.items() if k in self.__fieldnames } )
		self.supplementary = { k: v for k, v in kwargs.items() if k not in self.__fieldnames } | self.supplementary

	# len() support

	def __len__( self ) -> int:
		return len( self.supplementary ) + len( self.__regular_fieldnames )

	# getter

	def __getattr__( self, key: str ) -> Any:
		if key in self.__fieldnames:
			return super().__getattribute__( key )
		else:
			return self.supplementary.get( key )

	def __getitem__( self, key: str ):
		return self.__getattr__( key )

	# setter

	def __setitem__( self, key: str, value: Any ) -> None:
		self.__setattr__( key, value )

	def __setattr__( self, key, value ):
		if key in self.__fieldnames:
			super().__setattr__( key, value )
		else:
			self.supplementary[key] = value

	# dict-like methods

	def keys( self ) -> List[str]:
		return [*self.__regular_fieldnames, *self.supplementary.keys()]

	def values( self ) -> List[Any]:
		return [*[self.__getattr__( f ) for f in self.__regular_fieldnames], *self.supplementary.values()]

	def items( self ) -> List[Tuple[str, Any]]:
		return [*[( f, self.__getattr__( f ) ) for f in self.__regular_fieldnames ], *self.supplementary.items()]

	def as_dict( self ) -> Dict[str, Any]:
		d = { f: self.__getattr__( f ) for f in self.__regular_fieldnames } | self.supplementary
		return { k: v for k, v in d.items() if v is not None }

	# serialization

	@classmethod
	def from_dict( cls, obj: Dict[str, Any] ) -> Metadata:
		return Metadata.converter.structure( obj, Metadata )

	def to_dict( self ) -> Dict[str, Any]:
		return Metadata.converter.unstructure( self )

@define
class VirtualField:

	name: str = field( default=None )
	type: Type = field( default=None )
	default: Any = field( default=None )
	factory: Callable = field( default=None )
	description: str = field( default=None )
	display_name: str = field( default=None )
	expose: bool = field( default=True ) # expose field as regular property

	# enclosing: Type = field( default=None )

	def __call__( self, parent: Any = None ) -> Any:
		return self.value_for( parent )

	def value_for( self, parent: Any = None ) -> Any:
		if self.default:
			return self.default
		elif self.factory:
			return self.factory( parent )
		else:
			raise AttributeError( f'virtual field {self.name} has neither a default nor a factory' )

class VirtualFields( dict[str, VirtualField] ):

	def __init__( self ):
		super().__init__()
		self.__parent__ = None

	def __getattr__( self, name: str ) -> Any:
		try:
			return self.__getitem__( name )
		except KeyError:
			raise AttributeError

	def __contains__( self, item ) -> bool:
		return super().__contains__( item )

	def __getitem__( self, key: str ) -> VirtualField:
		vf = super().__getitem__( key )
		return vf.factory( self.__parent__ ) if vf.factory else vf.default

	def __setitem__( self, key: str, vf: VirtualField ) -> None:
		if not isinstance( vf, VirtualField ):
			raise ValueError( f'value must be of type {VirtualField}' )

		super().__setitem__( key, vf )

	def add( self, vf: VirtualField ) -> None:
		self[vf.name] = vf

	def set_field( self, name: str, vf: VirtualField ) -> None:
		self[name or vf.name] = vf

	def proxy( self, parent: Any ) -> VirtualFields:
		self.__parent__ = parent
		return self

@define
class VirtualFieldsBase( AttrsInstance ):

	__vf__: ClassVar[VirtualFields] = VirtualFields()

	@classmethod
	def VF( cls ) -> VirtualFields:
		return cls.__vf__

	@classmethod
	def fields( cls, include_virtual: bool = False, include_internal: bool = False, include_unexposed: bool = False ) -> List[Attribute | VirtualField]:
		_fields = fields( cls )
		if not include_internal:
			# _fields = filter( lambda f: not f.name.startswith( '_' ), _fields )
			_fields = [ f for f in _fields if not f.name.startswith( '_' ) ]

		_vfields = [ f for f in cls.__vf__.values() ] if include_virtual else []
		if not include_unexposed:
			_vfields = [ vf for vf in _vfields if vf.expose ]

		return [ *_fields, *_vfields ]

	@classmethod
	def field_names( cls, include_virtual: bool = False, include_internal: bool = False, include_unexposed: bool = False ) -> List[str]:
		return [f.name for f in cls.fields( include_virtual, include_internal, include_unexposed )]

	@classmethod
	def field_type( cls, field_name: str ) -> Any:
		if f := next( (f for f in cls.fields( True, True, True ) if f.name == field_name), None ):
			return f.type
		else:
			return None

	@classmethod
	def add_field( cls, vf: VirtualField, name: str = None ) -> None:
		cls.__vf__.set_field( name, vf )

	def __getattr__( self, name: str ) -> Any:
		if ( vf := self.__class__.__vf__.get( name ) ) and vf.expose:
			return vf.factory( self ) if vf.factory else vf.default
		else:
			raise AttributeError

	def getattr( self, name: str, quiet: bool = False, default: Any = None ) -> Any:
		try:
			return getattr( self, name )
		except AttributeError:
			if quiet:
				return default
			else:
				raise AttributeError

	def values( self, *field_names: str ) -> List[Any]:
		return [ self.getattr( f, quiet=True ) for f in field_names ]

	@property
	def vf( self ) -> VirtualFields:
		return self.__class__.__vf__.proxy( self )

def vproperty( **kwargs ):
	def inner( fn ):
		@property
		def wrap( *wargs, **wkwargs ):
			# fn is the decorated function, kwargs contains the keywords/values
			enclosing_cls: VirtualFieldsBase = wargs[0]
			enclosing_cls.__vf__.add( VirtualField(
				name = next( m[1] for m in getmembers( fn ) if m[0] == '__name__' ),
				type = kwargs.get( 'type' ) or signature( fn ).return_annotation,
				factory = fn,
				description = kwargs.get( 'description' ),
				display_name = kwargs.get( 'display_name' ),
				# enclosing= wargs[0],
			) )
			return fn( *wargs, **wkwargs )
		return wrap
	return inner

@define
class FieldFormatter:

	name: str = field( default=None )
	format: str = field( default=None )
	locale: str = field( default=None )

	formatter: Callable = field( default=None )

	def __call__( self, value: Any, format: str = None, locale: str = None ) -> Any:
		return self.__format__( value, format, locale )

	def __format__( self, value: Any, format: str = None, locale: str = None ) -> Any:
		return self.formatter( value, format or self.format, locale or self.locale )

class FieldFormatters( dict[str, FieldFormatter] ):

	__default_formatter_name__: ClassVar[str] = '__default__'
	__default_formatter__: ClassVar[FieldFormatter] = FieldFormatter( __default_formatter_name__, formatter=str )

	def __setitem__( self, key: str, field: FieldFormatter|Callable ) -> None:
		if not callable( field ):
			raise ValueError( f'value must be of type {FieldFormatter} or Callable' )

		if not isinstance( field, FieldFormatter ):
			field = FieldFormatter( name=key, formatter=field )

		super().__setitem__( key, field )

	def add( self, field: FieldFormatter ) -> None:
		self[field.name] = field

@define
class FormattedFieldsBase( AttrsInstance ):

	__fmf__: ClassVar[FieldFormatters] = FieldFormatters()

	@classmethod
	def field_formatters( cls ) -> FieldFormatters:
		return cls.__fmf__

	def format( self, name: str, fmt: str = None, locale: str = None, suppress_errors: bool = False ) -> str:
		if not ( formatter := self.__class__.__fmf__.get( name ) ):
			formatter = self.__class__.__fmf__.get( FieldFormatters.__default_formatter_name__ )

		if suppress_errors:
			try:
				return formatter( getattr( self, name ), fmt, locale )
			except Exception:
				return ''
		else:
			return formatter( getattr( self, name ), fmt, locale )

	def format_as_list( self, *fields, fmt: str = None, locale: str = None, conv: Callable = None, suppress_errors: bool = False ) -> List[str]:
		if conv:
			return [ conv( getattr( self, f ) ) for f in fields ]
		else:
			return [ self.format( f, fmt, locale, suppress_errors ) for f in fields ]

@define
class Keyword:

	name: str = field( default=None )
	description: Optional[str] = field( default=None )
	expr: str = field( default=None )
	fn: Callable = field( default=None )

	def __call__( self, *args, **kwargs ) -> str:
		if self.expr:
			return self.expr
		elif self.fn:
			return self.fn()
		else:
			raise TypeError( f'unable to call keyword {self.name}, neither expr or fn have appropriate values' )

@define
class Normalizer:

	name: str = field( default=None )
	type: Any = field( default=None )
	description: Optional[str] = field( default=None )
	fn: Callable = field( default=None )

	def __call__( self, *args, **kwargs ) -> str:
		return self.fn( *args, **kwargs )


# setup converters

Metadata.converter.register_unstructure_hook( datetime, toisoformat )
Metadata.converter.register_unstructure_hook( UID, lambda u: u.to_str() )

Metadata.converter.register_structure_hook( datetime, lambda dt, c: fromisoformat( dt ) )
Metadata.converter.register_structure_hook( UID, lambda uid, c: UID.from_str( uid ) )
