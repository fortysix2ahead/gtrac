
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar
from datetime import datetime
from datetime import timezone
from itertools import chain
from logging import getLogger
from pathlib import Path
from shutil import copy
from typing import Any
from typing import cast
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from click import confirm
from dataclass_factory import Factory
from dataclass_factory import Schema as FactorySchema
from fs.copy import copy_file
from fs.copy import copy_file_if
from fs.memoryfs import MemoryFS
from fs.multifs import MultiFS
from fs.osfs import OSFS
from orjson import loads
from rich import box
from rich.pretty import pretty_repr as pp
from rich.table import Table as RichTable
from tinydb import Query
from tinydb import TinyDB
from tinydb.operations import delete
from tinydb.operations import set as set_field
from tinydb.table import Document
from tinydb.table import Table

from .activity import Activity
from .activity_types import ActivityTypes
from .config import APPNAME
from .config import CLASSIFIER
from .config import console
from .config import KEY_GROUPS
from .config import KEY_SERVICE
from .filters import classifier as classifier_filter
from .filters import false as false_filter
from .filters import Filter
from .filters import parse_filters
from .filters import raw_id as raw_id_filter
from .filters import uid as uid_filter
from .registry import Registry
from .resources import Resource
from .resources import ResourceGroup
from .resources import ResourceType
from .rules_parser import parse_rules

log = getLogger( __name__ )

ACTIVITIES_NAME = 'activities.json'
INDEX_NAME = 'index.json'
METADATA_NAME = 'metadata.json'
RESOURCES_NAME = 'resources.json'
SCHEMA_NAME = 'schema.json'

DB_FILES = {
	ACTIVITIES_NAME: '{}',
	INDEX_NAME: '{}',
	METADATA_NAME: '{}',
	RESOURCES_NAME: '{}',
	SCHEMA_NAME: '{"version": 12}'
}

@dataclass
class Schema:

	version: int = field( default_factory=dict )
	# unknown: Dict = field( default_factory=dict )

@dataclass
class ActivityIndex:

	uid: Dict[str, Activity] = field( default_factory=dict )

@dataclass
class ResourceIndex:

	uid: Dict[str, List[Resource]] = field( default_factory=dict )
	uid_path: Dict[Tuple[str, str], Resource] = field( default_factory=dict )

@dataclass
class DbIndex:

	activities_table: InitVar[Table] = field( default=None )
	resources_table: InitVar[Table] = field( default=None )

	activities: ActivityIndex = field( default_factory=ActivityIndex )
	resources: ResourceIndex = field( default_factory=ResourceIndex )

	def __post_init__( self, activities_table: Table, resources_table: Table ):

		# clear dictionaries first, just in case we need to do a reindex later
		self.activities.uid.clear()
		self.resources.uid.clear()
		self.resources.uid_path.clear()

		for a in cast( List[Activity], activities_table.all() ):
			for uid in a.uids:
				if uid in self.activities.uid.keys():
					log.warning( f'{uid} referenced in activity {a.doc_id}, but is already referenced by activity {self.activities.uid[uid].doc_id}' )

				self.activities.uid[uid] = a

		for r in cast( List[Resource], resources_table.all() ):
			if r.uid not in self.resources.uid.keys():
				self.resources.uid[r.uid] = list()
			self.resources.uid[r.uid].append( r )

			if (r.uid, r.path) in self.resources.uid_path.keys():
				log.warning( f'{(r.uid, r.path)} referenced in resource {r.doc_id}, but is already referenced by resource {self.resources.uid_path[(r.uid, r.path)].doc_id}' )
			self.resources.uid_path[(r.uid, r.path)] = r

	def has_summaries( self, uid: str ) -> bool:
		for r in self.resources.uid.get( uid, [] ):
			if cast( ResourceType, Registry.resource_types.get( r.type )).summary:
				return True
		return False

	def has_recordings( self, uid: str ) -> bool:
		for r in self.resources.uid.get( uid, [] ):
			if not cast( ResourceType, Registry.resource_types.get( r.type )).summary:
				return True
		return False

class ActivityDb:

	def __init__( self, path: Optional[Path] = None, read_only: bool = False ):
		"""
		Creates an activity db, consisting of tiny db instances (meta + activities + resources + schema).

		:param path: directory containing db files
		:param read_only: read-only mode - does not allow write operations
		"""

		self._db_path = path
		self._read_only = read_only

		# setup db file system
		self._setup_db_filesystem()

		# initialize db factory
		self._init_db_factory()

		# initialize file systems
		self._init_db_filesystem()

		# load content from disk
		self._load_db()

		# index
		# self._index = DbIndex( self._activities, self._resources )

	def _setup_db_filesystem( self ):
		self.pkgfs = MemoryFS()
		for filename, contents in DB_FILES.items():
			self.pkgfs.writetext( f'/{filename}', contents )

		self.dbfs = MultiFS()
		# operating system FS
		if self._db_path:
			self._db_path.mkdir( parents=True, exist_ok=True )
			self.dbfs.add_fs( 'os', OSFS( root_path=str( self._db_path ) ), write=False )
			self.osfs = self.dbfs.get_fs( 'os' )
		else:
			self.osfs = None

		# memory FS as top layer
		self.dbfs.add_fs( 'mem', MemoryFS(), write=True )
		self.memfs = self.dbfs.get_fs( 'mem' )

	def _init_db_filesystem( self ):
		for f in DB_FILES:
			if self.osfs:
				if not self._read_only:
					copy_file_if( self.pkgfs, f'/{f}', self.osfs, f'/{f}', 'not_exists', preserve_time=True )
				copy_file( self.osfs, f'/{f}', self.memfs, f'/{f}', preserve_time=True )
			else:
				copy_file( self.pkgfs, f'/{f}', self.memfs, f'/{f}', preserve_time=True )

	def _init_db_factory( self ):
		self._factory = Factory(
			debug_path=True,
			schemas={
				# name_mapping={}, exclude=['doc_id']
				Activity: FactorySchema( omit_default=True, skip_internal=True, unknown='unknown' ),
				ActivityTypes: FactorySchema( parser=ActivityTypes.from_str, serializer=ActivityTypes.to_str ),
				Resource: FactorySchema( omit_default=True, skip_internal=True, unknown='unknown' ),
				Schema: FactorySchema( skip_internal=False ),
				# tiny db compatibility:
				# Schema: FactorySchema( name_mapping={ 'version': ( '_default', '1', 'version' ) }, skip_internal=False, unknown='unknown' ),
			}
		)

	def _load_db( self ):
		json = loads( self.memfs.readbytes( SCHEMA_NAME ) )
		self._schema = self._factory.load( json, Schema )

		json = loads( self.memfs.readbytes( RESOURCES_NAME ) )
		self._resources = self._factory.load( json, Dict[int, Resource] )

		json = loads( self.memfs.readbytes( ACTIVITIES_NAME ) )
		self._activities = self._factory.load( json, Dict[int, Activity] )

	# close db: persist changes to disk (if there are changes)

	# json flags: options = OPT_APPEND_NEWLINE | OPT_INDENT_2 | OPT_SORT_KEYS

	def save( self ):
		if self._read_only or self.osfs is None:
			return
		for f in DB_FILES:
			copy_file_if( self.memfs, f'/{f}', self.osfs, f'/{f}', 'newer' )

	def close( self ):
		self.save()

	# ---- DB Properties --------------------------------------------------------

	@property
	def db( self ) -> TinyDB:
		return self._db

	@property
	def index( self ) -> DbIndex:
		return self._index

	@property
	def resources_db( self ) -> TinyDB:
		return self._resources_db

	@property
	def metadata_db( self ) -> TinyDB:
		return self._metadata_db

	@property
	def schema( self ) -> Schema:
		return self._schema

	@property
	def metadata( self ) -> Table:
		return self._metadata

	@property
	def path( self ) -> Path:
		return self._activities_path.parent

	@property
	def db_path( self ) -> Path:
		return self._activities_path

	@property
	def activities_path( self ) -> Path:
		return self._activities_path

	@property
	def resources_path( self ) -> Path:
		return self._resources_path

	@property
	def metadata_path( self ) -> Path:
		return self._metadata_path

	@property
	def schema_path( self ) -> Path:
		return self._schema_path

	@property
	def activity_map( self ) -> Dict[int, Activity]:
		return self._activities

	@property
	def activities( self ) -> List[Activity]:
		return list( self._activities.values() )

	@property
	def activity_keys( self ) -> List[int]:
		return sorted( list( self._activities.keys() ) )

	@property
	def resources( self ) -> Table:
		return self._resources

	# ---- DB Operations --------------------------------------------------------

	# noinspection PyMethodMayBeStatic
	def _next_id( self, d: Dict ) -> int:
		keys = sorted( d.keys() )
		all_keys = range( 0, keys[-1] + 2 ) if keys else [0]
		return set( all_keys ).difference( set( keys ) ).pop()

	# insert activities

	def insert( self, *activities ) -> Union[int, List[int]]:
		ids = []
		for a in activities:
			a.id = self._next_id( self._activities )
			self._activities[a.id] = a
			ids.append( a.id )
		return ids[0] if len( ids ) == 1 else ids

	def insert_activity( self, activity: Activity ) -> int:
		return self.insert( activity )

	def insert_activities( self, activities: List[Activity] ) -> List[int]:
		return self.insert( *activities )

	# insert resources

	def insert_resource( self, r: Resource ) -> int:
		return self.resources.insert( r )

	# remove items

	def remove( self, a: Activity ) -> None:
		self._activities.remove( doc_ids=[a.doc_id] )

	def remove_field( self, a: Activity, field: str ) -> None:
		if field.startswith( '_' ):
			self._activities.update( set_field( field, None ), doc_ids=[a.doc_id] )
		else:
			self._activities.update( delete( field ), doc_ids=[a.doc_id] )

	def set_field( self, q: Query, field: str, value: Any ) -> List[int]:
		return self._activities.update( set_field( field, value ), cond=q )

	# -----

	def all( self ) -> List[Activity]:
		"""
		Retrieves all activities stored in the internal db.

		:return: list containing all activities
		"""
		return cast( List[Activity], self.activities.all() )

	def all_resources( self ) -> List[Resource]:
		return cast( List[Resource], self.resources.all() )

	def all_summaries( self ) -> List[Resource]:
		return [r for r in self.all_resources() if (rt := cast( ResourceType, Registry.resource_types.get( r.type ) )) and rt.summary]

	def all_uids( self ) -> List[str]:
		return list( set( [r.uid for r in self.all_resources()] ) )

	def contains( self, id: Optional[int] = None, raw_id: Optional[int] = None, classifier: Optional[str] = None, uid: Optional[str] = None, filters: Union[List[str], List[Filter], str, Filter] = None ) -> bool:
		filters = parse_filters( filters ) if filters else self._create_filter( id, raw_id, classifier, uid )
		for a in self.activities.all():
			if all( [f( a ) for f in filters] ):
				return True
		return False

	def contains_activity( self, uid: str, use_index: bool = False ) -> bool:
		if use_index:
			return uid in self.index.activities.uid.keys()
		else:
			return self.activities.contains( Query()['uids'].test( lambda v: True if uid in v else False ) )

	def get( self, id: Optional[int] = None, raw_id: Optional[int] = None, classifier: Optional[str] = None, uid: Optional[str] = None, filters: Union[List[str], List[Filter], str, Filter] = None ) -> Optional[Activity]:
		filters = parse_filters( filters ) if filters else self._create_filter( id, raw_id, classifier, uid )
		for a in self.activities.all():
			if all( [f( a ) for f in filters] ):
				return cast( Activity, a )
		return None

	def get_by_id( self, id: int ) -> Optional[Activity]:
		return self.activities.get( doc_id=id )

	def get_by_uid( self, uid: str, include_resources: bool = False ) -> Optional[Activity]:
		activity = cast( Activity, next( a for a in self.activities.all() if uid_filter( uid )( a ) ) )
		if activity and include_resources:
			activity.resources = self.get_resources_by_uid( uid )
		return activity

	def get_resource( self, id: int ) -> Optional[Resource]:
		return self.resources.get( doc_id=id )

	def get_resources_by_uid( self, uid ) -> List[Resource]:
		return cast( List[Resource], self.resources.search( Query()['uid'] == uid ) or [] )

	def _create_filter( self, id: Optional[int] = None, raw_id: Optional[int] = None, classifier: Optional[str] = None, uid: Optional[str] = None ) -> List[Filter]:
		if id and id > 0:
			return [Filter( 'id', id )]
		elif raw_id and raw_id > 0:
			return [uid_filter( f'{classifier}:{raw_id}' )] if classifier else [raw_id_filter( raw_id )]
		elif uid:
			return [uid_filter( uid )]
		else:
			return [false_filter()]

	# ----

	def find( self, filters: Union[List[str], List[Filter], str, Filter] = None ) -> [Activity]:
		all_activities = self.activities
		for r in parse_rules( *filters ):
			# all_activities = filter( r.evaluate, all_activities )
			all_activities = r.filter( all_activities )
		return list( all_activities )

	def find_by_classifier( self, classifier: str ) -> [Activity]:
		return self.find( classifier_filter( classifier ) )

	def find_ids( self, filters: Union[List[str], List[Filter], str, Filter] = None ) -> [int]:
		return [a.doc_id for a in self.find( filters )]

	def find_by_id( self, id: int = 0 ) -> Optional[Activity]:
		a = self.get( id=id ) if id > 0 else None  # try get by id
		a = self.get( raw_id=id ) if not a else a  # try get by raw id
		return a

	def find_last( self, service_name: Optional[str] ) -> Optional[Activity]:
		if service_name:
			_all = self.find( [f'{KEY_SERVICE}:{service_name}'] )
		else:
			_all = self.find( [] )

		_all = self.filter( _all, [Query().time.exists()] )
		return max( _all, key=lambda x: x.get( 'time' ) ) if len( _all ) > 0 else None

	def find_resource( self, uid: str, path: str = None ) -> Optional[Activity]:
		return self.resources.get( (Query()['uid'] == uid) & (Query()['path'] == path) )

	def find_resources( self, uid: str, path: str = None ) -> List[Resource]:
		if path:
			resources = self.resources.search( (Query()['uid'] == uid) & (Query()['path'] == path) )
		else:
			resources = self.resources.search( Query()['uid'] == uid )

		return cast( List[Resource], resources )

	def find_all_resources( self, uids: List[str] ) -> List[Resource]:
		return list( chain( *[self.resources.search( Query()['uid'] == uid ) for uid in uids] ) )

	def find_summaries( self, uid ) -> List[Resource]:
		return [r for r in self.find_resources( uid ) if (rt := cast( ResourceType, Registry.resource_types.get( r.type ) )) and rt.summary]

	def find_all_summaries( self, uids: List[str] ) -> List[Resource]:
		return [r for r in self.find_all_resources( uids ) if (rt := cast( ResourceType, Registry.resource_types.get( r.type ) )) and rt.summary]

	def find_all_resources_for( self, activities: Union[Activity, List[Activity]] ) -> List[Resource]:
		activities = [activities] if type( activities ) is Activity else activities
		return self.find_all_resources( list( chain( *[a.uids for a in activities] ) ) )

	def find_resource_group( self, uid: str, path: str = None ) -> ResourceGroup:
		return ResourceGroup( resources=self.find_resources( uid, path ) )

	def contains_resource( self, uid: str, path: str ) -> bool:
		return self.resources.contains( (Query()['uid'] == uid) & (Query()['path'] == path) )

	# noinspection PyMethodMayBeStatic
	def filter( self, activities: [Activity], queries: [Query] ) -> [Activity]:
		for q in queries or []:
			activities = list( filter( q, activities or [] ) )
		return activities

	def query( self, queries: [Query] ) -> [Activity]:
		if len( queries ) == 0:
			query = Query().noop()
		else:
			query = queries[0]
			for q in queries[1:]:
				query = query & q

		return self._activities.search( query )

# ---- DB Factory ---

def document_cls( doc: Union[Dict, Document], doc_id: int ) -> Type:
	if classifier := doc.get( CLASSIFIER ):
		if classifier == 'group':  # ActvityGroup is registered with 'groups' todo: improve!
			classifier = KEY_GROUPS
		if classifier in Registry.document_classes:
			return Registry.document_classes.get( classifier )
	elif groups := doc.get( KEY_GROUPS ):
		if 'ids' in groups.keys() or 'uids' in groups.keys():
			return Registry.document_classes.get( KEY_GROUPS )

	return Document

def document_factory( doc: Union[Dict, Document], doc_id: int ) -> Document:
	return document_cls( doc, doc_id )( doc, doc_id )

# ---- DB Operations ----

def backup_db( db_file: Path, backup_dir: Path ) -> None:
	backup_dir.mkdir( parents=True, exist_ok=True )
	backup_file = Path( backup_dir, f"{APPNAME}.db.{datetime.now( timezone.utc ).strftime( '%Y%m%d_%H%M%S' )}.json" )
	copy( db_file, backup_file )
	log.info( f"created database backup in {backup_file}" )

def restore_db( db: TinyDB, db_file: Path, backup_dir: Path, force: bool ) -> None:
	backup_dir.mkdir( parents=True, exist_ok=True )
	glob_pattern = f'{APPNAME}.db.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].json'
	files = list( backup_dir.glob( glob_pattern ) )
	if len( files ) > 0:
		files.sort( reverse=True )
		log.info( f'restoring backup from {files[0].name}' )
		if not force:
			if not confirm( f'Restore database from {files[0].name}? The current state will be overwritten!' ):
				log.info( f"database restore from {files[0].name} aborted ..." )
				return

		db.close()
		copy( files[0], db_file )
		log.info( f"database restored from {files[0].name}" )
	else:
		log.info( f"no backups found in {backup_dir}" )

def status_db( db: ActivityDb ) -> None:
	table = RichTable( box=box.MINIMAL, show_header=False, show_footer=False )
	table.add_row( 'activities in database', pp( len( db.all() ) ) )
	for s in Registry.service_names():
		activities = list( db.find_by_classifier( s ) )
		table.add_row( f'activities from {s}', pp( len( activities ) ) )

	console.print( table )
