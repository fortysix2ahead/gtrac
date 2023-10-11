from __future__ import annotations

from enum import Enum
from re import compile, Pattern
from typing import Any, Dict, List, Optional, Tuple, Type

from attrs import Attribute, define, field, fields

from tracs.uid import UID

# todo: not sure if we still need the status
class ResourceStatus( Enum ):
	UNKNOWN = 100
	EXISTS = 200
	NO_CONTENT = 204
	NOT_FOUND = 404

pattern: Pattern = compile( '\w+/(vnd\.(?P<vendor>\w+).)?((?P<subtype>\w+)\+)?(?P<suffix>\w+)' )
classifier_local_id_pattern = compile( '\w+:\d+' )

@define
class ResourceType:

	# type/subtype
	# type "/" [tree "."] subtype ["+" suffix]* [";" parameter]

	type: str = field( default=None )
	subtype: str = field( default=None )
	suffix: str = field( default=None )
	vendor: str = field( default=None )

	activity_cls: Type = field( default=None )
	name: str = field( default=None )

	summary: bool = field( default=False )
	recording: bool = field( default=False )
	image: bool = field( default=False )

	def __attrs_post_init__( self ):
		if self.subtype or self.suffix or self.vendor:
			return
		if self.type and (m := pattern.match( self.type )):
			self.suffix = m.groupdict().get( 'suffix' )
			self.subtype = m.groupdict().get( 'subtype' )
			self.vendor = m.groupdict().get( 'vendor' )

	def extension( self ) -> Optional[str]:
		if self.suffix and self.subtype:
			return f'{self.subtype}' if not self.vendor else f'{self.subtype}.{self.suffix}'
		else:
			return self.suffix

	@property
	def other( self ) -> bool:
		return True if not self.summary and not self.recording and not self.image else False

@define
class Resource:

	id: int = field( default=None )
	name: Optional[str] = field( default=None )
	type: str = field( default=None )
	path: str = field( default=None )
	source: Optional[str] = field( default=None )
	summary: bool = field( default=False )
	uid: str = field( default=None )

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
	__uid__: UID = field( default=None, kw_only=True, alias='__uid__' )

	def __attrs_post_init__( self ):
		if self.__uid__:
			self.uid, self.path = self.__uid__.clspath, self.__uid__.path
		elif self.uid and self.path:
			self.__uid__ = UID( uid=f'{self.uid}/{self.path}' )
		else:
			raise AttributeError( 'attributes uid and path are necessary' )

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
	def parents( self ) -> Any: # todo: would be nice to return Activity here ...
		return self.__parents__

	@property
	def classifier( self ) -> str:
		return self.__uid__.classifier

	@property
	def local_id( self ) -> int:
		return self.__uid__.local_id

	@property
	def local_id_str( self ) -> str:
		return str( self.local_id )

	# todo: rename, that's not a good name
	@property
	def uidpath( self ) -> str:
		return self.__uid__.uid

	def as_text( self, encoding: str = 'UTF-8' ) -> Optional[str]:
		return self.content.decode( encoding )

	def summaries( self ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.summary), None )

	def recordings( self ) -> List[Resource]:
		return [r for r in self.resources if not r.summary]

	def get_child( self, resource_type: str ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.type == resource_type), None )

@define
class Resources:
	"""
	Dict-like container for resources.
	"""

	data: List[Resource] = field( factory=list )

	__uid_map__: Dict[str, Resource] = field( factory=dict, init=False, alias='__uid_map__' )

	def __attrs_post_init__( self ):
		for r in self.data:
			self.__uid_map__[r.uid] = r

	# magic/dict methods

	def __len__( self ) -> int:
		return len( self.data )

	def __getitem__( self, item: str ):
		return self.__uid_map__[item]

	def get( self, item: str ):
		return self.__uid_map__.get( item )

	def keys( self ):
		return list( self.__uid_map__.keys() )

	def values( self ):
		return list( self.data )

	# add/remove etc.

	def add( self, *resources: Resource ):
		for r in resources:
			if r.uidpath in self.__uid_map__:
				raise KeyError( f'resource with UID {r.uidpath} already contained in resources' )

			r.id = _next_id( self.data )
			self.data.append( r )
			self.__uid_map__[r.uidpath] = r

	# access methods

	# todo: change the sort order later?
	def all( self, sort = False ) -> List[Resource]:
		return list( self.data ) if not sort else sorted( self.data, key=lambda r: str( r.id ) )

	def all_for( self, uid: str = None, path: str = None ) -> List[Resource]:
		_all = filter( lambda r: r.uid == uid, self.all() ) if uid else self.all()
		_all = filter( lambda r: r.path == path, _all ) if path else _all
		return list( _all )

	def summary( self ) -> Optional[Resource]:
		return next( (r for r in self.data if r.summary), None )

	def summaries( self ) -> List[Resource]:
		return [r for r in self.data if r.summary]

	def recordings( self ) -> List[Resource]:
		return [r for r in self.data if not r.summary]


def _next_id( resources: List[Resource] ) -> int:
	existing_ids = [r.id for r in resources]
	id_range = range( 1, max( existing_ids ) + 2 ) if len( existing_ids ) > 0 else [1]
	return set( id_range ).difference( set( existing_ids ) ).pop()
