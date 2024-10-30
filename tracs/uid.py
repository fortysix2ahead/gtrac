from __future__ import annotations

from typing import Callable, ClassVar, List, Optional, Tuple
from urllib.parse import SplitResult, urlsplit, urlunsplit

from attrs import define, field
from cattrs import Converter, GenConverter
from fs.path import basename

@define( eq=False, order=False )
class UID:

	converter: ClassVar[Converter] = GenConverter()

	classifier: str = field( default=None )
	"""Classifier is equal to the url scheme. Example: uid = polar:101, classifier = polar."""
	local_id: int = field( default=None )
	"""Identifier of an activity, equal to the path. Example: uid = polar:101, local_id = 101."""
	path: str = field( default=None )
	"""Path of a resource of an activity. Example: uid = polar:101?recording.gpx, path = recording.gpx."""
	part: int = field( default=None )
	"""Part number of an activity. Example: uid = polar:101#2, part = 2."""

	def __attrs_post_init__( self ):
		# always parse classifier
		classifier, local_id, path, part = self._uidparse( self.classifier )
		# overwrite fields depending on provided and parsed values
		self.classifier = classifier # always
		self.local_id = self.local_id if self.local_id else local_id
		self.path = self.path if self.path else path
		self.part = self.part if self.part else part

	# noinspection PyMethodMayBeStatic
	def _urlsplit( self, url: str ) -> SplitResult:
		url: SplitResult = urlsplit( url )
		if not url.scheme and url.path:
			if ':' in url.path:
				path, local_id = url.path.split( ':' )
				return SplitResult( scheme=path, netloc=url.netloc, path=local_id, query=url.query, fragment=url.fragment )
			else:
				return SplitResult( scheme=url.path, netloc=url.netloc, path='', query=url.query, fragment=url.fragment )
		else:
			return url

	def _uidparse( self, url: str  ) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[int]]:
		url: SplitResult = self._urlsplit( url )
		classifier = url.scheme if url.scheme else None
		path_split = url.path.split( '/', maxsplit=1 )
		local_id = int( path_split[0] ) if path_split[0] else None
		path = path_split[1] if len( path_split ) > 1 else None
		part = int( url.fragment ) if url.fragment else None
		return classifier, local_id, path, part

	def __eq__( self, other ):
		return self.uid == other.uid if isinstance( other, UID ) else self.uid == other

	def __hash__( self ) -> int:
		return hash( self.uid )

	def __lt__( self, other: [UID|str] ):
		return self.uid < other.uid if isinstance( other, UID ) else self.uid < other

	def __gt__( self, other ):
		return self.uid > other.uid if isinstance( other, UID ) else self.uid > other

	def __str__( self ) -> str:
		return self.uid

	@property
	def uid( self ):
		return self.as_str

	@property
	def head( self ) -> str:
		return f'{self.classifier}:{self.local_id}' if self.local_id else self.classifier

	@property
	def tail( self ) -> Optional[str]:
		if self.path and self.part:
			return f'{self.path}#{self.part}'
		elif self.path:
			return self.path
		elif self.part:
			return str( self.part )
		else:
			return None

	@property
	def base( self ) -> UID:
		return UID( self.classifier, self.local_id, basename( self.path ), self.part )

	def resolve( self, fn: Callable ) -> UID:
		return UID( self.classifier, self.local_id, fn( self.local_id, basename( self.path ) ), self.part )

	@property
	def as_str( self ) -> str:
		if self.classifier and not self.local_id:
			return urlunsplit( ['', '', self.classifier, self.path or '', self.part or ''] )
		else:
			local_id = str( self.local_id ) if self.local_id else ''
			path = f'{local_id}/{self.path}' if self.path else local_id
			part = str( self.part ) if self.part else ''
			return urlunsplit( [self.classifier, '', path, '', part] )

	@property
	def as_tuple( self ) -> Tuple[str, int]:
		return self.classifier, self.local_id

	@property
	def as_tuple_str( self ) -> str:
		return f'{self.classifier}:{self.local_id}' if self.local_id else self.classifier

	@property
	def as_triple( self ) -> Tuple[str, int, str]:
		return self.classifier, self.local_id, self.path

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

	# serialization

	def to_str( self ):
		return UID.converter.unstructure( self )

	@staticmethod
	def from_str( obj: str ) -> UID:
		return UID.converter.structure( obj, UID )

	@staticmethod
	def from_strs( objs: List[str] ) -> List[UID]:
		return [UID.converter.structure( u, UID ) for u in objs]

# setup converter

UID.converter.register_unstructure_hook( UID, lambda u: str( u ) )
UID.converter.register_structure_hook( UID, lambda u, v: UID( u ) )
