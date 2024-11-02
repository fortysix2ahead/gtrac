from __future__ import annotations

from datetime import timedelta
from logging import getLogger
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from cattrs.preconf.orjson import make_converter
from more_itertools import last, rstrip
from orjson import dumps as save_json, loads as load_json, OPT_APPEND_NEWLINE, OPT_INDENT_2, OPT_SORT_KEYS

from tracs.handlers import ResourceHandler
from tracs.pluginmgr import importer, resourcetype
from tracs.resources import ResourceType
from tracs.utils import timedelta_to_str

log = getLogger( __name__ )

JSON_TYPE = 'application/json'

@resourcetype
def json_resource_type() -> ResourceType:
	return ResourceType( type=JSON_TYPE )

@importer( type=JSON_TYPE )
class JSONHandler( ResourceHandler ):

	TYPE: str = JSON_TYPE
	OPTIONS = OPT_APPEND_NEWLINE | OPT_INDENT_2 | OPT_SORT_KEYS

	def load_raw( self, content: Union[bytes,str], **kwargs ) -> Any:
		return load_json( content )

	def save_raw( self, data: Any, **kwargs ) -> bytes:
		return save_json( data, option=JSONHandler.OPTIONS, default=serialize )

	# additional helpers for json access

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

	def str( self, *args, parent: Dict = None, default=None ) -> Optional[str]:
		return self._value( *args, parent=parent, conv=str, default=default )

class DataclassFactoryHandler( JSONHandler ):

	def __init__( self ):
		super().__init__()
		self.converter = make_converter()

	def load_data( self, raw: Any, **kwargs ) -> Any:
		"""
		Transforms raw data into structured data. If raw data is a dict and an activity class is set, it will use
		the dataclass factory to try a transformation. Will return raw data in case that fails.
		Example: transform a dict into a dataclass.
		"""
		try:
			return self.converter.structure( raw, self.__class__.ACTIVITY_CLS )
		except RuntimeError:
			log.error( f'unable to transform raw data into structured data by using the factory for {self._activity_cls}', exc_info=True )
			return raw

def serialize( obj: Any ):
	if isinstance( obj, timedelta ):
		return timedelta_to_str( obj )
	raise TypeError
