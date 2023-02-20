from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar
from datetime import datetime
from datetime import timezone
from importlib.resources import path as resource_path
from itertools import chain
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
from logging import getLogger
from pathlib import Path
from rich import box
from rich.pretty import pretty_repr as pp
from rich.table import Table as RichTable

from tinydb import TinyDB
from tinydb import Query
from tinydb.operations import delete
from tinydb.operations import set as set_field
from tinydb.storages import JSONStorage
from tinydb.table import Document
from tinydb.table import Table

from .activity import Activity
from .resources import Resource
from .resources import ResourceGroup
from .config import CLASSIFIER
from .config import KEY_GROUPS
from .config import console
from .config import APPNAME
from .config import TABLE_NAME_DEFAULT
from .config import KEY_SERVICE
from .config import KEY_VERSION
from .db_storage import DataClassStorage
from .filters import Filter
from .filters import classifier as classifier_filter
from .filters import false as false_filter
from .filters import parse_filters
from .filters import raw_id as raw_id_filter
from .filters import uid as uid_filter
from .registry import Registry
from .resources import ResourceType

log = getLogger( __name__ )

ACTIVITIES_NAME = 'activities.json'
METADATA_NAME = 'metadata.json'
RESOURCES_NAME = 'resources.json'
SCHEMA_NAME = 'schema.json'

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

	def __init__( self, path: Path = None, activities_name: str = None, metadata_name: str = None, resources_name: str = None, schema_name: str = None, pretend: bool = False ):
		"""
		Creates an activity db, consisting of tiny db instances (meta + activities + resources + schema).

		:param path: directory containing dbs
		:param pretend: pretend mode - allows write operations, but does not persist anything to disk
		:param cache: enable db caching
		:param passthrough: plain mode, opens activity db without middleware
		"""

		# names
		self._activities_name = activities_name if activities_name else ACTIVITIES_NAME
		self._metadata_name = metadata_name if metadata_name else METADATA_NAME
		self._resources_name = resources_name if resources_name else RESOURCES_NAME
		self._schema_name = schema_name if schema_name else SCHEMA_NAME

		with resource_path( __package__, '__init__.py' ) as pkg_path:
			self._db_resource_path = Path( pkg_path.parent, 'db' )
			if path:
				self._activities_path = Path( path, self._activities_name )
				self._metadata_path = Path( path, self._metadata_name )
				self._resources_path = Path( path, self._resources_name )
				self._schema_path = Path( path, self._schema_name )

				path.mkdir( parents=True, exist_ok=True )

				if not self._schema_path.exists():
					copy( Path( self._db_resource_path, SCHEMA_NAME ), self._schema_path )
				if not self._activities_path.exists():
					copy( Path( self._db_resource_path, ACTIVITIES_NAME ), self._activities_path )
				if not self._metadata_path.exists():
					copy( Path( self._db_resource_path, METADATA_NAME ), self._metadata_path )
				if not self._resources_path.exists():
					copy( Path( self._db_resource_path, RESOURCES_NAME ), self._resources_path )
			else:
				self._activities_path = Path( self._db_resource_path, ACTIVITIES_NAME )
				self._resources_path = Path( self._db_resource_path, RESOURCES_NAME )
				self._metadata_path = Path( self._db_resource_path, METADATA_NAME )
				self._schema_path = Path( self._db_resource_path, SCHEMA_NAME )

				pretend = True  # turn on in-memory mode when path is not provided

		# init schema db
		self._default_schema: TinyDB = TinyDB( storage=JSONStorage, path=Path( self._db_resource_path, SCHEMA_NAME ), access_mode='r' )
		self._default_schema_version = self._default_schema.all()[0][KEY_VERSION]
		self._schema: TinyDB = TinyDB( storage=JSONStorage, path=self._schema_path, access_mode='r' )
		self._schema_version = self._schema.all()[0][KEY_VERSION]

		# init activities db
		self._db: TinyDB = TinyDB( storage=DataClassStorage, path=self._activities_path, read_only=pretend, passthrough=True )
		self._storage: DataClassStorage = cast( DataClassStorage, self._db.storage )
		self._activities = self.db.table( TABLE_NAME_DEFAULT )
		self._activities.document_class = Activity

		# init resources db
		self._resources_db: TinyDB = TinyDB( storage=DataClassStorage, path=self._resources_path, read_only=pretend, passthrough=True )
		self._resources = self._resources_db.table( TABLE_NAME_DEFAULT )
		self._resources.document_class = Resource

		# init resources db
		self._metadata_db: TinyDB = TinyDB( storage=JSONStorage, path=self._metadata_path, access_mode='r' )
		self._metadata = self._metadata_db.table( TABLE_NAME_DEFAULT )

		# index
		self._index = DbIndex( self._activities, self._resources )

	# ---- DB Properties --------------------------------------------------------

	@property
	def db( self ) -> TinyDB:
		return self._db

	@property
	def index( self ) -> DbIndex:
		return self._index

	@property
	def activities_db( self ) -> TinyDB:
		return self._db

	@property
	def resources_db( self ) -> TinyDB:
		return self._resources_db

	@property
	def metadata_db( self ) -> TinyDB:
		return self._metadata_db

	@property
	def schema_db( self ) -> TinyDB:
		return self._schema

	@property
	def default_schema_db( self ) -> TinyDB:
		return self._default_schema

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
	def storage( self ) -> DataClassStorage:
		return cast( DataClassStorage, self._db.storage )

	@property
	def activities( self ) -> Table:
		return self._activities

	@property
	def resources( self ) -> Table:
		return self._resources

	@property
	def schema( self ) -> int:
		return self._schema_version

	@property
	def default_schema( self ) -> int:
		return self._default_schema_version

	# ---- DB Operations --------------------------------------------------------

	def insert( self, docs: Union[Activity, List[Activity]] ) -> Union[int, List[int]]:
		docs = [docs] if isinstance( docs, Activity ) else docs

		doc_ids = self.activities.insert_multiple( docs )
		for doc, doc_id in zip( docs, doc_ids ):
			doc.doc_id = doc_id

		return doc_ids if len( doc_ids ) > 1 else doc_ids[0]

	def insert_activity( self, activity: Activity ) -> int:
		doc_id = self.activities.insert( activity )
		activity.doc_id = doc_id
		return doc_id

	def insert_activities( self, activities: List[Activity] ) -> List[int]:
		doc_ids = self.activities.insert_multiple( activities )
		for doc, doc_id in zip( activities, doc_ids ):
			doc.doc_id = doc_id
		return doc_ids

	def insert_resource( self, r: Resource ) -> int:
		return self.resources.insert( r )

	def upsert_resource( self, r: Resource ) -> List[int]:
		return self.resources.upsert( r, (Query().uid == r.uid) & (Query().path == r.path) )

	def upsert_activity( self, a: Activity, doc_id: Optional[int] = None, uid: Optional[str] = None ) -> None:
		if doc_id is not None and doc_id > 0:
			self.activities.upsert( Document( dict( a ), doc_id=doc_id ) )
		elif a.doc_id > 0:
			self.activities.upsert( Document( dict( a ), doc_id=a.doc_id ) )
		elif uid is not None:
			self.activities.upsert( dict( a ), cond=Query().uids.any( [ uid ] ) )
		elif a.uid is not None:
			self.activities.upsert( dict( a ), cond=Query().uids.any( [ a.uid ] ) )
		elif a.uids is not None:
			self.activities.upsert( dict( a ), cond=Query().uids.test( lambda v: set( a.uids ) == set( v ) ) )

	def update( self, a: Activity ) -> None:
		self.activities.update( dict( a ), doc_ids=[a.doc_id] )

	def update_resource( self, r: Resource ) -> None:
		self.resources.update( dict( r ), doc_ids=[r.doc_id] )

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

	def all_activities( self ) -> List[Activity]:
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
		parsed_filters = parse_filters( filters or [] )
		all_activities = self.activities.all()
		for f in parsed_filters:
			all_activities = filter( f, all_activities )
		return all_activities

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

	# close all

	def close( self ):
		self._db.close()
		self._resources_db.close()
		self._metadata_db.close()
		self._schema.close()

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

def create_metadb( path: Path = None, use_memory_storage: bool = False ) -> TinyDB:
	return TinyDB( storage=DataClassStorage, path=path, read_only=use_memory_storage, passthrough=False )

def create_db( path: Path = None, use_memory_storage: bool = False, passthrough=False ) -> TinyDB:
	return TinyDB( storage=DataClassStorage, path=path, read_only=use_memory_storage, passthrough=passthrough )

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
