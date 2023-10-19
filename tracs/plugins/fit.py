
from logging import getLogger
from typing import Any

from tracs.activity import Activity
from tracs.registry import importer, resourcetype
from tracs.handlers import ResourceHandler

log = getLogger( __name__ )

FIT_TYPE = 'application/fit'

@resourcetype( type=FIT_TYPE )
class FITActivity( Activity ):

	def __raw_init__( self, raw: Any ) -> None:
		pass

@importer( type=FIT_TYPE )
class FITImporter( ResourceHandler ):

	TYPE: str = FIT_TYPE
	ACTIVITY_CLS = FITActivity
