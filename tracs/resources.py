from __future__ import annotations

from enum import Enum
from functools import cached_property
from re import compile, Pattern
from typing import Any, ClassVar, Dict, List, Optional, Union

from attrs import Attribute, define, field, fields
from cattrs import Converter, GenConverter

from tracs.uid import UID

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

	id: int = field( default=None ) # todo: to be removed
	name: Optional[str] = field( default=None )
	type: str = field( default=None )
	path: str = field( default=None )
	source: Optional[str] = field( default=None )
	status: Optional[int] = field( default=None )
	summary: bool = field( default=False ) # todo: to be removed
	uid: Union[str, UID] = field( default=None )

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
		if type( self.uid ) is UID:  # uid of type UID is allowed
			self.uid, self.path = self.uid.clspath, self.uid.path

		if self.uid_obj.denotes_resource():
			self.uid, self.path = self.uid_obj.clspath, self.uid_obj.path

		if self.uid_obj.denotes_activity():
			raise AttributeError( 'resource UID may not denote an activity without a proper path' )

		if self.uid_obj.denotes_service():
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
		return self.uid_obj.classifier

	@property
	def local_id( self ) -> int:
		return self.uid_obj.local_id

	@property
	def local_id_str( self ) -> str:
		return str( self.local_id )

	@cached_property
	def uid_obj( self ) -> UID:
		return UID( uid=self.uid, path=self.path )

	# todo: rename, that's not a good name
	@property
	def uidpath( self ) -> str:
		return self.uid_obj.uid

	def as_text( self, encoding: str = 'UTF-8' ) -> Optional[str]:
		return self.content.decode( encoding )

	def get_child( self, resource_type: str ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.type == resource_type), None )

	# serialization

	@classmethod
	def from_dict( cls, obj: Dict[str, Any] ) -> Resource:
		return Resource.converter.structure( obj, Resource )

	def to_dict( self ) -> Dict[str, Any]:
		return Resource.converter.unstructure( self )

class Resources( list[Resource] ):

	def __init__( self, *resources: Resource, lst: Optional[List[Resource]] = None, lists: Optional[List[Resources]] = None ):
		super().__init__()
		# for convenience, allow creation with given resources/list/resource lists
		self.extend( resources )
		self.extend( lst or [] )
		self.extend( [r for l in lists or [] for r in l] )

	def summary( self ) -> Optional[Resource]:
		return next( (r for r in self if r.summary), None )

	def summaries( self ) -> List[Resource]:
		return [r for r in self if r.summary]

	def recording( self ) -> Resource:
		return next( (r for r in self if r.recording), None )

	def recordings( self ) -> List[Resource]:
		return [r for r in self if r.recording]

	def image( self ) -> Optional[Resource]:
		return next( (r for r in self if r.image), None )

	def images( self ) -> List[Resource]:
		return [r for r in self if r.image]

	# access

	# for compatibility only
	def all( self ) -> List[Resource]:
		return [ r for r in self ]

	def all_for( self, uid: str = None, path: str = None ) -> List[Resource]:
		_all = filter( lambda r: r.uid == uid, self ) if uid else self
		_all = filter( lambda r: r.path == path, _all ) if path else _all
		return list( _all )

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

Resource.converter.register_structure_hook( UID, lambda obj, cls: UID.from_str( obj ) )
Resource.converter.register_structure_hook( Union[str, UID], lambda obj, cls: obj if isinstance( obj, str ) else UID.from_str( obj ) )
