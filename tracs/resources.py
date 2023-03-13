from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar
from enum import Enum
from re import compile
from re import Pattern
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from urllib.parse import urlparse

# todo: not sure if we still need the status
class ResourceStatus( Enum ):
	UNKNOWN = 100
	EXISTS = 200
	NO_CONTENT = 204
	NOT_FOUND = 404

pattern: Pattern = compile( '\w+\/(vnd\.(?P<vendor>\w+).)?((?P<subtype>\w+)\+)?(?P<suffix>\w+)' )

@dataclass
class UID:

	uid: str = field( default=None )
	classifier: str = field( default=None )
	local_id: int = field( default=None )
	path: str = field( default=None )
	part: int = field( default=None )

	def __post_init__( self ):
		if self.uid:
			url = urlparse( self.uid )
			if url.scheme:
				self.classifier = url.scheme
				self.local_id = int( url.path ) if url.path else None
				self.path = url.query if url.query else None
				self.part = int( url.fragment ) if url.fragment else None
			else:
				self.classifier = url.path

		elif self.classifier and self.local_id:
			self.uid = f'{self.classifier}:{self.local_id}'
			if self.path:
				self.uid = f'{self.uid}?{self.path}'
			if self.part:
				self.uid = f'{self.uid}#{self.part}'

	def __str__( self ) -> str:
		return self.uid

	def denotes_service( self, service_names: List[str] = None ) -> bool:
		is_service = True if self.classifier and not self.local_id and not self.path else False
		if service_names:
			return is_service if self.classifier in service_names else False
		else:
			return is_service

	def denotes_activity( self ) -> bool:
		return True if self.classifier and self.local_id and not self.path else False

	def denotes_resource( self ) -> bool:
		return True if self.classifier and self.local_id and self.path else False

	def denotes_part( self ) -> bool:
		return True if self.classifier and self.local_id and self.part else False

@dataclass
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

	def __post_init__( self ):
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

@dataclass
class Resource:

	name: Optional[str] = field( default=None )
	type: str = field( default=None )
	path: str = field( default=None )
	source: str = field( default=None )
	status: int = field( default=None )
	summary: bool = field( default=False )
	uid: str = field( default=None )

	# additional field holding data of a resource, used when loading, but won't be persisted in db
	raw: Any = field( default=None, repr=False )  # structured data making up this resource
	content: bytes = field( default=None, repr=False )  # raw content as bytes
	text: InitVar = field( default=None, repr=False )  # decoded content as string, to be removed

	resources: List[Resource] = field( default_factory=list, repr=False )

	def __post_init__( self, text: str ):
		self.content = text.encode( encoding='UTF-8' ) if text else self.content

	def __hash__( self ):
		return hash( (self.uid, self.path) )

	@property
	def classifier( self ) -> str:
		return self._uid()[0]

	@property
	def local_id( self ) -> int:
		return int( self._uid()[1] )

	@property  # property should be deprecated in favour of local id
	def raw_id( self ) -> int:
		return self.local_id

	def _uid( self ) -> Tuple[str, str]:
		classifier, raw_id = self.uid.split( ':', maxsplit=1 )
		return classifier, raw_id

	def as_text( self, encoding: str = 'UTF-8' ) -> Optional[str]:
		return self.content.decode( encoding )

	def summaries( self ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.summary), None )

	def recordings( self ) -> List[Resource]:
		return [r for r in self.resources if not r.summary]

	def get_child( self, resource_type: str ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.type == resource_type), None )

@dataclass
class ResourceGroup:
	resources: List[Resource] = field( default_factory=list )

	def summary( self ) -> Optional[Resource]:
		return next( (r for r in self.resources if r.summary), None )

	def recordings( self ) -> List[Resource]:
		return [r for r in self.resources if not r.summary]
