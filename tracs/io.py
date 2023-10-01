from logging import getLogger
from typing import List, Union

from attrs import define, field
from cattrs.gen import make_dict_structure_fn, make_dict_unstructure_fn, override
from cattrs.preconf.orjson import make_converter
from fs.base import FS
from orjson import OPT_APPEND_NEWLINE, OPT_INDENT_2, OPT_SORT_KEYS

from tracs.resources import Resource, Resources
from tracs.uid import UID

log = getLogger( __name__ )

ORJSON_OPTIONS = OPT_APPEND_NEWLINE | OPT_INDENT_2 | OPT_SORT_KEYS

RESOURCES_NAME = 'resources.json'
RESOURCES_PATH = f'/{RESOURCES_NAME}'
SCHEMA_NAME = 'schema.json'
SCHEMA_PATH = f'/{SCHEMA_NAME}'

RESOURCE_CONVERTER = make_converter()
SCHEMA_CONVERTER = make_converter()

# converter configuration

# resource

resource_structure_hook = make_dict_structure_fn(
	Resource,
	RESOURCE_CONVERTER,
	_cattrs_forbid_extra_keys=True,
)

RESOURCE_CONVERTER.register_structure_hook( Union[str, UID], lambda obj, cls: obj ) # uid should always be a str, so return the obj untouched

resource_unstructure_hook = make_dict_unstructure_fn(
	Resource,
	RESOURCE_CONVERTER,
	_cattrs_omit_if_default=True,
	content=override( omit=True ),
	data=override( omit=True ),
	raw=override( omit=True ),
	resources=override( omit=True ),
	status=override( omit=True ),
	summary=override( omit=True ),
	text=override( omit=True ),
	__parents__=override( omit=True ),
	__uid__=override( omit=True ),
)

RESOURCE_CONVERTER.register_unstructure_hook( Resource, resource_unstructure_hook )

# resource handling

def load_resources( fs: FS ) -> Resources:
	try:
		resources = RESOURCE_CONVERTER.loads( fs.readbytes( RESOURCES_PATH ), List[Resource] )
		log.debug( f'loaded {len( resources )} resource entries from {RESOURCES_NAME}' )
		return Resources( data = resources )
	except RuntimeError:
		log.error( f'error loading db', exc_info=True )

def write_resources( resources: Resources, fs: FS ) -> None:
	fs.writebytes( RESOURCES_PATH, RESOURCE_CONVERTER.dumps( resources.all( sort=True ), unstructure_as=List[Resource], option=ORJSON_OPTIONS ) )
	log.debug( f'wrote {len( resources )} resource entries to {RESOURCES_NAME}' )

# schema handling

@define
class Schema:

	version: int = field( default=None )

def load_schema( fs: FS ) -> Schema:
	schema = SCHEMA_CONVERTER.loads( fs.readbytes( SCHEMA_PATH ), Schema )
	log.debug( f'loaded database schema from {SCHEMA_PATH}, schema version = {schema.version}' )
	return schema