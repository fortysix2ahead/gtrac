
from pathlib import Path
from logging import getLogger
from shutil import copy
from sys import exit
from sys import modules

from rich.prompt import Confirm

from .config import ApplicationContext
from .db import ACTIVITIES_NAME
from .db import ActivityDb
from .db import METADATA_NAME
from .db import RESOURCES_NAME
from .db import SCHEMA_NAME
from .plugins.handlers import JSONHandler
from .utils import timestring

log = getLogger( __name__ )

def migrate_application( ctx: ApplicationContext, function_name: str = None, force: bool = False ):
	if not function_name:
		if ctx.db.schema != ctx.db.default_schema:
			function_name = f'_migrate_{ctx.db.schema}_{ctx.db.default_schema}'
		else:
			return

	current_db = ctx.db
	migration_name = f'migration_{timestring()}'
	next_db_path = Path( current_db.path.parent, f'db_{migration_name}' )
	next_db_path.mkdir( parents=True, exist_ok=True )

	copy( current_db.activities_path, Path( next_db_path, ACTIVITIES_NAME ) )
	copy( current_db.metadata_path, Path( next_db_path, METADATA_NAME ) )
	copy( current_db.resources_path, Path( next_db_path, RESOURCES_NAME ) )
	copy( current_db.schema_path, Path( next_db_path, SCHEMA_NAME ) )

	next_db = ActivityDb( path=next_db_path )

	if function_name and function_name in dir( modules[ __name__ ] ):
		if force or Confirm.ask( f'migration function {function_name} found, would you like to execute the migration?' ):
			getattr( modules[ __name__ ], function_name )( current_db, next_db )
	else:
		log.error( f'migration function "{function_name}" not found in module {__name__}' )

	exit( 0 )

def _migrate_11_12( current_db, next_db ):
	pass

def consolidate_ids( current_db, next_db ):
	json = JSONHandler().load( path=current_db.activities_path ).raw

	activity_list = []
	for doc_id, a in json.raw['_default'].items():
		activity_list.append( ( doc_id, None, a ) )

	activity_list = sorted( activity_list, key = lambda t: t[2]['time'] )

	new_dict = {}
	for index in range( len( activity_list ) ):
		new_index = str( index + 1 )
		new_dict[new_index] = activity_list[index][2]
	new_dict = { '_default': new_dict }

	JSONHandler().save( data = new_dict, path=Path( current_db.activities_path.parent, 'activities_consolidated.json' ) )

def deduplicate( current_db, next_db ):
	next_db.close()
	activities: dict = JSONHandler().load( path=next_db.activities_path ).raw
	resources: dict = JSONHandler().load( path=next_db.resources_path ).raw

	keys = {}
	for key in sorted( activities.get( '_default' ).keys() ):
		a = activities.get( '_default' ).get( key )
		for uid in a.get( 'uids', [] ):
			if uid not in keys:
				keys[uid] = key
			else:
				del( activities.get( '_default' )[key] )
				log.info( f'removed duplicate activitiy {uid}, doc_id {key}' )

	keys = {}
	for key in sorted( resources.get( '_default' ).keys() ):
		r = resources.get( '_default' ).get( key )
		if (r['uid'], r['path']) not in keys:
			keys[(r['uid'], r['path'])] = key
		else:
			del (resources.get( '_default' )[key])
			log.info( f"removed duplicate resource {(r['uid'], r['path'])}, doc_id {key}" )

	JSONHandler().save( activities, next_db.activities_path )
	JSONHandler().save( resources, next_db.resources_path )

def migrate_resources( current_db, next_db ):
	json = JSONHandler().load( path=current_db.activities_path ).raw
	resource_json = JSONHandler().load( path=current_db.resources_path ).raw

	table = json['_default']
	resource_table = resource_json['_default']
	resource_counter = 1

	for doc_id, doc in table.items():
		classifier = doc.get( 'classifier' )
		raw_id = doc.get( 'raw_id' )
		resources = doc.get( 'resources' )
		resource_ids = []

		if classifier != 'group':
			for r in resources:
				r['uid'] = f'{classifier}:{raw_id}'
				resource_table[str( resource_counter )] = r
				resource_ids.append( resource_counter )
				resource_counter += 1
			if len( resource_ids ) > 0:
				doc['resources'] = resource_ids

	items = list( table.items() )
	for doc_id, doc in items:
		classifier = doc.get( 'classifier' )
		if classifier == 'group':
			doc['uids'] = doc['group_uids']

			del (doc['classifier'])
			del( doc['raw_id'] )
			del( doc['resources'] )
			del( doc['metadata'] )
			del( doc['group_ids'] )
			del( doc['group_uids'] )
		else:
			if doc.get( 'parent_id', 0 ) > 0:
				del( table[doc_id] )
			else:
				doc['uids'] = [f'{doc.get( "classifier" )}:{doc.get( "raw_id" )}']
				del (doc['classifier'])
				del (doc['raw_id'])
				del (doc['resources'])
				del (doc['metadata'])

	#JSONHandler().save( Path( current_db.activities_path.parent, 'test.json' ), json )
	JSONHandler().save( Path( current_db.activities_path ), json )
	JSONHandler().save( current_db.resources_path, resource_json )
