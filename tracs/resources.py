from __future__ import annotations

from enum import Enum
from functools import cached_property
from logging import getLogger
from re import compile, Pattern
from typing import Any, Callable, ClassVar, Dict, List, Optional, Union

from attrs import Attribute, define, evolve, field, fields
from cattrs import Converter, GenConverter
from cattrs.gen import make_dict_unstructure_fn, override
from fs.base import FS
from fs.errors import ResourceNotFound
from fs.path import basename, split
from more_itertools import unique
from more_itertools.more import first, last, rstrip

from tracs.protocols import Exporter, Importer
from tracs.uid import UID

log = getLogger( __name__ )

# todo: not sure if we still need the status
class Status( Enum ):
	UNKNOWN = 100
	EXISTS = 200
	NO_CONTENT = 204
	NOT_FOUND = 404

TYPE_PATTERN: Pattern = compile( r'\w+/(vnd\.(?P<vendor>\w+).)?((?P<subtype>\w+)\+)?(?P<suffix>\w+)' )

@define
class ResourceType:
	# type/subtype
	# type "/" [tree "."] subtype ["+" suffix]* [";" parameter]

	type: str = field( default=None )
	name: str = field( default=None )

	summary: bool = field( default=False )
	recording: bool = field( default=False )
	image: bool = field( default=False )

	def __attrs_post_init__( self ):
		if not TYPE_PATTERN.match( self.type ):
			raise ValueError

	@cached_property
	def subtype( self ) -> Optional[str]:
		return TYPE_PATTERN.match( self.type ).groupdict().get( 'subtype' )

	@cached_property
	def suffix( self ) -> Optional[str]:
		return TYPE_PATTERN.match( self.type ).groupdict().get( 'suffix' )

	@cached_property
	def vendor( self ) -> Optional[str]:
		return TYPE_PATTERN.match( self.type ).groupdict().get( 'vendor' )

	@cached_property
	def ext( self ) -> Optional[str]:
		if self.suffix and self.subtype:
			return f'{self.subtype}' if not self.vendor else f'{self.subtype}.{self.suffix}'
		else:
			return self.suffix

	def extension( self ) -> Optional[str]:
		return self.ext

class ResourceTypes( dict[str, ResourceType] ):

	_instance: ClassVar[ResourceTypes] = None

	@classmethod
	def inst( cls ):
		if not cls._instance:
			cls._instance = ResourceTypes()
		return cls._instance

	@classmethod
	def images( cls ) -> List[ResourceType]:
		return [rt for rt in cls.inst().values() if rt.image]

	@classmethod
	def recordings( cls ) -> List[ResourceType]:
		return [rt for rt in cls.inst().values() if rt.recording]

	@classmethod
	def summaries( cls ) -> List[ResourceType]:
		return [rt for rt in cls.inst().values() if rt.summary]

@define
class Resource:

	converter: ClassVar[Converter] = GenConverter( omit_if_default=True )

	name: str = field( default=None )
	type: str = field( default=None )
	path: str = field( default=None )
	source: str = field( default=None )
	status: int = field( default=None )
	# field type is actually UID, str is only allowed in constructor
	uid: UID|str = field( default=None, converter=lambda u: UID.from_str( u ) if isinstance( u, str ) else u )

	# additional fields holding data of a resource, used during load

	content: bytes = field( default=None, repr=False, kw_only=True )
	"""Raw content as bytes"""
	text: str = field( default=None, repr=False, kw_only=True )
	"""Decoded content as string, can be used to initialize a resource from string"""
	raw: Any = field( default=None, repr=False, kw_only=True )
	"""Structured data making up this resource, will be converted from content."""
	data: Any = field( default=None, repr=False, kw_only=True )
	"""Secondary field as companion to raw, might contain another form of structured data, i.e. a dataclass in parallel to a json"""

	__parents__: List = field( factory=list, repr=False, init=False, alias='__parents__' )
	__dict__: Dict = field( factory=dict, repr=False, init=False ) # property cache

	def __attrs_post_init__( self ):
		# move path information from uid to resource, we may change this later
		if not self.path and self.uid:
			self.path = self.uid.path
			self.uid.path = None # always remove path in UID

		if self.uid and self.uid.denotes_activity() and self.path is None:
			raise AttributeError( 'resource UID may not denote an activity without having a path' )

		if self.uid and self.uid.denotes_service():
			raise AttributeError( 'resource UID may not denote a service' )

		# todo: really needed?
		self.content = self.text.encode( encoding='UTF-8' ) if self.text else self.content

	def __hash__( self ):
		return hash( (self.uid, self.path) )

	# class methods

	@classmethod
	def fields( cls ) -> List[Attribute]:
		return list( fields( Resource ) )

	@classmethod
	def fieldnames( cls ) -> List[str]:
		return [f.name for f in fields( Resource )]

	# additional properties

	@property
	def parents( self ) -> Any:  # todo: would be nice to return Activity here ...
		return self.__parents__

	@property
	def classifier( self ) -> str:
		return self.uid.classifier

	@property
	def local_id( self ) -> int:
		return self.uid.local_id

	@property
	def local_id_str( self ) -> str:
		return str( self.local_id )

	@cached_property
	def fpath( self ) -> Optional[str]:
		return split( self.path )[1] if self.path else None

	@cached_property
	def uid_obj( self ) -> UID:
		return self.uid

	@cached_property
	def as_uid( self ) -> UID:
		return UID( self.uid.classifier, self.uid.local_id, self.fpath or self.uid.path )

	# todo: rename, that's not a good name
	@cached_property
	def uidpath( self ) -> str:
		return str( self.as_uid )

	def as_text( self, encoding: str = 'UTF-8' ) -> Optional[str]:
		return self.content.decode( encoding )

	def get_child( self, resource_type: str ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.type == resource_type), None )

	# helper for convenient data access (only when raw field contains a dict)

	def _value( self, *args, parent: Dict = None, conv: Callable, default: Any = None ) -> Any:
		parent, item = parent or self.raw, last( args )
		for s in rstrip( args, lambda e: e is item ):
			parent = parent[s]

		try:
			return conv( val ) if ( val := parent[item] ) not in [ '', None, 0, 0.0 ] else default
		except (KeyError, TypeError, ValueError):
			return default

	def float( self, *args, parent: Dict = None, default=None ) -> Optional[float]:
		return self._value( *args, parent=parent, conv=float, default=default )

	def list( self, *args, parent: Dict = None, default=None ) -> Optional[List]:
		return self._value( *args, parent=parent, conv=list, default=default )

	def int( self, *args, parent: Dict = None, default=None ) -> Optional[int]:
		return self._value( *args, parent=parent, conv=int, default=default )

	# can't name this method str() because of cattrs weirdness ...

	def strg( self, *args, parent: Dict = None, default=None ) -> Optional[str]:
		return self._value( *args, parent=parent, conv=str, default=default )

	# serialization

	# todo: path argument can be removed later
	def load( self, fs: FS, path: str, importer: Importer, resolver: Optional[Callable] = None ) -> None:
		path = path or self.path
		path = resolver( path ) if resolver else path
		try:
			importer.load( fs=fs, path=path, resource=self )
		except (FileNotFoundError, ResourceNotFound):
			log.error( f'unable to load resource {self} from FS {fs}' )

	def unload( self ) -> None:
		"""
		Removes any content from this resource.

		:return: None
		"""
		self.content, self.text, self.raw, self.data = None, None, None, None

	def unload_to( self, fs: FS, path: str ) -> None:
		try:
			fs.writebytes( path, self.content )
			self.unload()
		except TypeError:
			log.error( f'unable to unload resource {self} to {fs}/{path}' )

	def save( self, fs: FS, path: str, exporter: Exporter ) -> None:
		exporter.save( data=self.data, path=path, fs=fs, resource=self ) # todo: add exception handling here

	@classmethod
	def from_dict( cls, obj: Dict[str, Any] ) -> Resource:
		return Resource.converter.structure( obj, Resource )

	def to_dict( self ) -> Dict[str, Any]:
		return Resource.converter.unstructure( self )

	def evolve( self ) -> Resource:
		return evolve( self, content=None, text=None, raw=None, data=None )

class Resources( list[Resource] ):

	def __init__( self, *resources: Resource, lst: Optional[List[Resource]] = None, lists: Optional[List[Resources]] = None ):
		super().__init__()
		# for convenience, allow creation with given resources/list/resource lists
		self.extend( resources )
		self.extend( lst or [] )
		self.extend( [r for l in lists or [] for r in l] )

	def iter( self ):
		"""
		Iterates over all resources in the resource list.
		:return:
		"""
		return iter( self )

	def iter_for( self, uid: UID|str ) -> Resources:
		"""
		Iterates over all resources in this list where the head of the uid matches the provided UID's head.
		:param uid:
		:return:
		"""
		uid = uid if isinstance( uid, UID ) else UID( uid )
		return Resources( *[r for r in self if r.uid.head == uid.head] )
		# return [ r for r in self if r.uid.head == uid.head ]

	def iter_types( self, types:List[str] ) -> Resources:
		return Resources( *[r for r in self if r.type in types] )

	def iter_uids( self ) -> List[UID]:
		return [UID( r.uid.classifier, r.uid.local_id, basename( r.path ) or basename( r.uid.path ) ) for r in self]

	def iter_uids_for( self, uid: UID|str ) -> List[UID]:
		uid = uid if isinstance( uid, UID ) else UID( uid )
		return [ u for u in self.iter_uids() if u.head == uid.head ]

	def iter_uid_heads( self ) -> List[UID]:
		return [r.uid for r in unique( self, key=lambda r: r.uid )]

	def iter_paths( self ) -> List[str]:
		return [r.path or r.uid.path for r in self]

	# access

	# for compatibility only
	def all( self ) -> List[Resource]:
		return [ r for r in self ]

	def all_for( self, uid: str = None, path: str = None ) -> List[Resource]:
		_all = filter( lambda r: r.uid == uid, self ) if uid else self
		_all = filter( lambda r: r.path == path, _all ) if path else _all
		return list( _all )

	def first( self ) -> Optional[Resource]:
		return first( self, None )

	@classmethod
	def from_list( cls, *lists: Resources ) -> Resources:
		return Resources( lst=[r for l in lists for r in l] )

	# serialization

	@classmethod
	def from_dict( cls, obj: List[Dict[str, Any]] ) -> Resources:
		return Resources( *[ Resource.from_dict( r ) for r in obj ] )

	def to_dict( self ) -> List[Dict[str, Any]]:
		return [ r.to_dict() for r in self ]

# configure converters

Resource.converter.register_unstructure_hook( UID, lambda uid: uid.to_str() )
Resource.converter.register_unstructure_hook( UID|str, lambda uid: uid.to_str() )

Resource.converter.register_structure_hook( UID, lambda obj, cls: UID.from_str( obj ) )
Resource.converter.register_structure_hook( Union[str, UID], lambda obj, cls: obj if isinstance( obj, str ) else UID.from_str( obj ) )
hook = make_dict_unstructure_fn(
	Resource,
	Resource.converter,
	_cattrs_omit_if_default=True,
	content=override( omit=True ),
	data=override( omit=True ),
	raw=override( omit=True ),
	status=override( omit=True ),
	text=override( omit=True ),
)
Resource.converter.register_unstructure_hook( Resource, hook )
