
from csv import field_size_limit, reader as csv_reader
from typing import Any, Union

from tracs.handlers import ResourceHandler
from tracs.pluginmgr import importer, resourcetype
from tracs.resources import ResourceType

CSV_TYPE = 'text/csv'

DEFAULT_FIELD_SIZE_LIMIT = 131072

# register CSV type
@resourcetype
def csv_resource_type() -> ResourceType:
	return ResourceType( type=CSV_TYPE )

# todo: replace with @importer / remove duplicate type/cls information from here
@importer( type=CSV_TYPE )
class CSVHandler( ResourceHandler ):

	TYPE: str = CSV_TYPE

	def __init__( self, *args, **kwargs ) -> None:
		super().__init__( *args, **kwargs )
		self._field_size_limit = kwargs.get( 'field_size_limit', DEFAULT_FIELD_SIZE_LIMIT ) # keep this later use

	def load_raw( self, content: Union[bytes,str], **kwargs ) -> Any:
		return [ r for r in csv_reader( self.as_str( content ).splitlines() ) ]

	@property
	def field_size_limit( self ) -> int:
		return self._field_size_limit

	@field_size_limit.setter
	def field_size_limit( self, limit: int ) -> None:
		self._field_size_limit = limit
		field_size_limit( self._field_size_limit )
