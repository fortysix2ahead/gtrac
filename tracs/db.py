
from __future__ import annotations

from itertools import chain, groupby
from logging import getLogger
from pathlib import Path
from typing import cast, Dict, List, Mapping, Optional, Tuple, Union

from fs.base import FS
from fs.copy import copy_file, copy_file_if
from fs.errors import ResourceNotFound
from fs.memoryfs import MemoryFS
from fs.multifs import MultiFS
from fs.osfs import OSFS
from fs.path import basename
from more_itertools import first_true, unique
from orjson import dumps, OPT_APPEND_NEWLINE, OPT_INDENT_2, OPT_SORT_KEYS
from rich import box
from rich.pretty import pretty_repr as pp
from rich.table import Table as RichTable
from rule_engine import Rule

from tracs.activity import Activities, Activity
from tracs.config import ApplicationContext
from tracs.fsio import load_activities, load_schema, Schema, write_activities
from tracs.migrate import migrate_db, migrate_db_functions
from tracs.resources import Resource, Resources
from tracs.uid import UID

log = getLogger( __name__ )

ORJSON_OPTIONS = OPT_APPEND_NEWLINE | OPT_INDENT_2 | OPT_SORT_KEYS

ACTIVITIES_NAME = 'activities.json'
SCHEMA_NAME = 'schema.json'

SCHEMA_VERSION = 14

DB_FILES = {
	ACTIVITIES_NAME: dumps( [] ),
	SCHEMA_NAME: dumps( { "version": SCHEMA_VERSION } )
}

UNDERLAY = 'underlay'
OVERLAY = 'overlay'

class ActivityDbIndex:

	UID_TO_ACTIVITY: Dict[str, Activity] = {}
	UID_TO_RESOURCE: Dict[str, List[Resource]] = {}
	UID_PATH_TO_RESOURCE: Dict[Tuple[str,str], Resource] = {}

	def __init__( self, activity_map: Dict[int, Activity], resource_map: Dict[int, Resource] ):
		self.__class__.UID_TO_ACTIVITY = { uid: a for a in activity_map.values() for uid in a.uids }
		self.__class__.UID_TO_RESOURCE = { uid: list( it ) for uid, it in groupby( resource_map.values(), key=lambda r: r.uid ) }
		self.__class__.UID_PATH_TO_RESOURCE = { (r.uid, r.path) for r in resource_map.values() }

		self._relate_activities()

	def _relate_activities( self ):
		for uid, activity in self.UID_TO_ACTIVITY.items():
			activity.__resources__ = self.UID_TO_RESOURCE.get( uid, [] )
			for r in activity.__resources__:
				r.__parent_activity__ = activity

class ActivityDb:

	def __init__( self, path: Optional[Union[Path, str]] = None, fs: Optional[FS] = None, read_only: bool = False, enable_index: bool = False, **kwargs ):
		"""
		Creates an activity db, consisting of tiny db instances (meta + activities + resources + schema).

		:param path: directory containing db files, may be a Path or a string
		:param fs: instead of providing a path, it's also possible to provide the internally used filesystem object
		:param read_only: read-only mode - does not allow write operations
		:param enable_index: experimental, not used at the moment
		"""

		self._path = path
		self._fs = fs
		self._read_only = read_only

		# initialize db file system(s)
		self._fs = self._init_fs()

		# load content from disk
		self._load_db()

		# sets of types in order to classify resources
		self._summary_types, self._recording_types = set(), set()
		self.register_summary_types( *( kwargs.get( 'summary_types' ) or set() ) )
		self.register_recording_types( *( kwargs.get( 'recording_types') or set() ) )

		# experimental: create index and setup relations between resources and activities, turned off for now
		if enable_index:
			pass
			# log.debug( f'creating db index' )
			# self._index = ActivityDbIndex( self.activity_map, self.resource_map )

	def _init_fs( self ):
		log.debug( f'initializing db file system from path = {self._path} and ready_only = {self._read_only}' )

		# operating system fs as underlay (resp. memory when no path is provided)
		if self._path:
			if self._read_only:
				return self._init_readonly_filesystem( self._path )
			else:
				return self._init_filesystem( self._path )
		else:
			if self._fs:
				return self._init_existing_fs( self._fs )
			else:
				return self._init_inmemory_filesystem()

	def _init_filesystem( self, path: Path ) -> FS:
		fs = MultiFS()
		fs.add_fs( UNDERLAY, OSFS( root_path=str( self._path ), create=True ), write=False )
		fs.add_fs( OVERLAY, MemoryFS(), write=True )

		for file, content in DB_FILES.items():
			if not fs.get_fs( UNDERLAY ).exists( f'/{file}' ):
				fs.get_fs( UNDERLAY ).writebytes( f'/{file}', content )
			# copy_file_if( self.pkgfs, f'/{f}', self.underlay_fs, f'/{f}', 'not_exists', preserve_time=True )

		# todo: this is probably not needed?
		for f in DB_FILES.keys():
			copy_file( fs.get_fs( UNDERLAY ), f'/{f}', fs.get_fs( OVERLAY ), f'/{f}', preserve_time=True )

		return fs

	def _init_readonly_filesystem( self, path: Path ) -> FS:
		if not path.exists():
			log.error( f'error opening db from {self._path} in read-only mode: path does not exist' )
			raise ResourceNotFound( str( path ) )

		osfs = OSFS( root_path=str( self._path ) )
		fs = MemoryFS()

		for f in DB_FILES.keys():
			try:
				copy_file( osfs, f'/{f}', fs, f'/{f}', preserve_time=True )
			except ResourceNotFound:
				fs.writebytes( f, DB_FILES.get( f ) )

		return fs

	# noinspection PyMethodMayBeStatic
	def _init_existing_fs( self, fs: FS ) -> FS:
		for file, content in DB_FILES.items():
			if not fs.exists( file ):
				fs.writebytes( file, content )
		return fs

	# for development only ...
	# noinspection PyMethodMayBeStatic
	def _init_inmemory_filesystem( self ) -> FS:
		return self._init_existing_fs( MemoryFS() )

	def _load_db( self ):
		self._schema = load_schema( self.fs )
		self._activities: Activities = load_activities( self.fs )

	def register_summary_types( self, *types: str ):
		[ self._summary_types.add( t ) for t in types ]

	def register_recording_types( self, *types: str ):
		[ self._recording_types.add( t ) for t in types ]

	# todo: remove do_commit flag?
	def commit( self, do_commit: bool = True ):
		if do_commit:
			write_activities( self._activities, self.overlay_fs )

	def save( self ):
		if self._read_only or self.underlay_fs is None:
			return
		for f in DB_FILES:
			copy_file_if( self.overlay_fs, f'/{f}', self.underlay_fs, f'/{f}', 'newer' )

	def close( self ):
		# self.commit() # todo: really do auto-commit here?
		self.save()

	# ---- FS Properties ----

	@property
	def fs( self ) -> FS:
		return self._fs

	@property
	def underlay_fs( self ) -> FS:
		if isinstance( self.fs, MultiFS ):
			return cast( MultiFS, self.fs ).get_fs( UNDERLAY )
		else:
			return self._fs

	@property
	def overlay_fs( self ) -> FS:
		if isinstance( self.fs, MultiFS ):
			return cast( MultiFS, self.fs ).get_fs( OVERLAY )
		else:
			return self._fs

	@property
	def schema( self ) -> Schema:
		return self._schema

	# properties for content access

	@property
	def activity_map( self ) -> Mapping[int, Activity]:
		return self._activities.id_map()

	@property
	def activities( self ) -> List[Activity]:
		return list( self._activities.all() )

	@property
	def activity_keys( self ) -> List[int]:
		return sorted( list( self._activities.ids() ) )

	@property
	def activity_ids( self ) -> List[int]:
		return sorted( list( self._activities.id_keys() ) )

	@property
	def resources( self ) -> Resources:
		return Resources( lst = [r for a in self.activities for r in a.resources] )

	# ---- DB Operations --------------------------------------------------------

	# noinspection PyMethodMayBeStatic
	def _next_id( self, d: Dict ) -> int:
		key_range = range( 1, max( d.keys() ) + 2 ) if d.keys() else [1]
		return set( key_range ).difference( set( d.keys() ) ).pop()

	# insert/upsert activities

	def insert( self, *activities ) -> List[int]:
		return self._activities.add( *activities )

	def insert_activity( self, activity: Activity ) -> int:
		return self.insert( activity )[0]

	def insert_activities( self, activities: List[Activity] ) -> List[int]:
		return [ self.insert_activity( a ) for a in activities ]

	def upsert( self, *activities ) -> int|List[int]:
		return l[0] if len( l := [self.upsert_activity( a ) for a in activities] ) == 1 else l

	def upsert_activity( self, activity: Activity ) -> int:
		#if existing := self.get_by_uid( activity.uid ):
		if existing := self.get_for_uid( activity.uid ):
			if existing.group:
				Activity.group_of( existing, activity, target=existing )
			else:
				Activity.union_of( activity, target=existing, force=True )
			return existing.id
		else:
			return self.insert_activity( activity )

	def upsert_activities( self, activities: List[Activity] ) -> List[int]:
		return [ self.upsert_activity( a ) for a in activities ]

	# def replace_activity( self, new: Activity, old: Activity = None, id: int = None, uid = None ) -> None:
	# 	self._activities.replace( new, old, id, uid )

	# remove items

	def remove_activity( self, a: Activity ) -> None:
		self._activities.remove( a.id )

	def remove_activities( self, activities: List[Activity], auto_commit: bool = False ) -> None:
		[self.remove_activity( a ) for a in activities]
		self.commit( auto_commit )

	# -----

	@property
	def summaries( self ) -> List[Resource]:
		"""
		Returns all resource of type summary.
		:return: all summaries
		"""
		# return [r for r in self.resources if (rt := cast( ResourceType, Registry.instance().resource_types.get( r.type ) )) and rt.summary]
		return [r for r in self.resources if r.type in self._summary_types ]

	@property
	def recordings( self ) -> List[Resource]:
		"""
		Returns all resources of type recording.
		:return: all recordings
		"""
		return [r for r in self.resources if r.type in self._recording_types]

	@property
	def uids( self, classifier: str = None ) -> List[str]:
		"""
		Returns a list of all known uids.
		Optionally restrict the list to contain only resources with the given classifier.
		"""
		if classifier:
			return list( set( [r.uid for r in self.resources if r.classifier == classifier] ) )
		else:
			return list( set( [r.uid for r in self.resources] ) )

	def contains( self, uid: UID|str ) -> bool:
		uid = uid if isinstance( uid, UID ) else UID.from_str( uid )
		if uid.denotes_activity():
			return self.contains_activity( uid )
		elif uid.denotes_resource():
			return self.contains_resource( uid, None )
		else:
			return False

	def contains_activity( self, uid: UID|str ) -> bool:
		uid = uid if isinstance( uid, UID ) else UID.from_str( uid )
		return any( u == uid for u in self._activities.iter_uids() )

	def contains_resource( self, uid: UID|str, path: Optional[str] ) -> bool:
		if isinstance( uid, UID ):
			uid = UID( uid.classifier, uid.local_id, path or uid.path )
		else:
			uid = UID( uid, path=path if path else None )
		return any( (u == uid or u.base == uid.base) for u in self._activities.iter_resource_uids() )

	# get methods

	def get( self, id: Optional[int] = None, uid: Optional[str] = None ) -> Optional[Activity|List[Activity]]:
		"""
		Convenience get. Intendend to be used with one kwarg.
		"""
		if id:
			return self.get_by_id( id )
		elif uid:
			return self.get_by_uid( uid )

	def get_by_id( self, id: int ) -> Optional[Activity]:
		"""
		Returns the (first and only) activity with the provided id.
		There should never be two activities with the same id.
		:param id: id of the activity
		"""
		return first_true( self.activities, pred=lambda a: a.id == id )

	def get_by_uid( self, uid: UID|str ) -> Optional[Activity]:
		"""
		Returns the activity with the uid equal to the provided uid.
		This method does not treat any uids which appear as group members.
		:param uid: uid of the activity
		"""
		return first_true( self.activities, pred=lambda a: a.uid == uid )

	def get_for_uid( self, uid: UID|str ) -> Optional[Activity]:
		"""
		Returns the first activity for the given uid.
		This includes activities with the uid equal to the provided uid as well as activities
		where the uid appears as member (groups and multiparts).
		:param uid:
		:return:
		"""
		return first_true( self._activities, pred=lambda a: uid in [ a.uid, *a.metadata.members ] )

	def get_group_for_uid( self, uid: UID|str ) -> Optional[Activity]:
		"""
		Returns the first group where the given uid appears as member.
		This does not include activities with the uid equal to the provided.
		:param uid:
		:return:
		"""
		return first_true( self._activities, pred=lambda a: uid in a.metadata.members )

	def get_resource_by_uid_path( self, uid: UID|str, path: str ) -> Optional[Resource]:
		"""
		Returns the resource with the provided uid and path.
		:param uid:
		:param path:
		:return:
		"""
		return next( (r for r in self.find_resources_by_uid( uid ) if r.path == path), None )

	# several find methods to make life easier

	# find activities

	def find( self, rules: List[Rule] = None ) -> List[Activity]:
		all_activities = self.activities
		for r in rules:
			# all_activities = filter( r.evaluate, all_activities )
			all_activities = r.filter( all_activities )
		return list( all_activities )

	def find_by_id( self, ids: List[int] ) -> List[Activity]:
		"""
		Returns all activities with ids contained in the provided list of ids
		:param ids:
		:return:
		"""
		return [ a for a in self._activities if a.id in ( ids or [] ) ]

	def find_by_uid( self, uids: List[str] ) -> List[Activity]:
		"""
		Returns all activities with uids contained in the provided list of uids
		This method does not treat any uids which appear as group members.
		:param uids:
		:return:
		"""
		return [ a for a in self._activities if a.uid in ( uids or [] ) ]

	def find_for_uid( self, uid: UID|str ) -> List[Activity]:
		"""
		Returns all activities for the given uid.
		This includes activities with the uid equal to the provided uid as well as activities
		where the uid appears as member (groups and multiparts)
		:param uid:
		:return:
		"""
		return [ a for a in self._activities if ( uid in [ a.uid, *a.metadata.members ] ) ] if uid else []

	def find_groups_for_uid( self, uid: Optional[str] ) -> List[Activity]:
		"""
		Returns all groups for the given uid.
		This includes does not include activities with the uid equal to the provided.
		:param uid:
		:return:
		"""
		return [a for a in self._activities if uid in a.metadata.members ] if uid else []

	def find_by_classifier( self, classifier: str ) -> List[Activity]:
		"""
		Finds all activities, which have a certain classifier (originate from a certain service, i.e. polar).
		"""
		return [a for a in self._activities if any( uid.startswith( classifier ) for uid in a.iter_uid_heads )]

	def find_first( self, classifier: Optional[str] = None ) -> Optional[Activity]:
		"""
		Finds the oldest activity. Optionally restricts itself to activities with the given classifier.
		"""
		activities = self.find_by_classifier( classifier ) if classifier else self.activities
		return min( activities, key=lambda a: a.starttime )

	def find_last( self, classifier: Optional[str] = None ) -> Optional[Activity]:
		"""
		Finds the newest activity. Optionally restricts itself to activities with the given classifier.
		"""
		activities = self.find_by_classifier( classifier ) if classifier else self.activities
		return max( activities, key=lambda a: a.starttime )

	# find resources

	# todo: create a universal method, like get from above
	def find_resources( self, uid: str, path: Optional[str] = None ) -> List[Resource]:
		"""
		Finds resources having the given uid and optionally the given path.
		"""
		resources = [ r for r in self.resources if r.uid == uid ]
		if path:
			resources = [ r for r in resources if r.path == path ]
		return resources

	def find_resources_by_uid( self, uid: UID|str ) -> Resources:
		"""
		Returns all resources of the activity with the provided uid.
		:param uid:
		:return:
		"""
		return a.resources if ( a:= self.get_by_uid( uid ) ) else []

	def find_resources_by_uids( self, uids: List[UID|str] ) -> Resources:
		"""
		Returns all resources with the provided uids.
		:param uids:
		:return:
		"""
		return Resources( *chain( *[self.find_resources_by_uid( uid ) for uid in uids] ) )

	def find_resources_of_type( self, *types: str ) -> Resources:
		"""
		Finds all resources of the given type.
		"""
		return Resources( *[r for r in self._activities.iter_resources() if r.type in types] )

	def find_resources_for( self, uid: UID|str ) -> Resources:
		"""
		Finds all resources for a given UID. This included all resources when the activity is part of a group.
		"""
		uid = uid if isinstance( uid, UID ) else UID( uid )
		resources = [r for a in self.find_for_uid( uid ) for r in a.resources if uid in [a.uid.head, r.uid.head if r.uid else None ] ]
		return Resources( *unique( resources, key=lambda r: r.path ) )

	def find_recordings( self, *uids: Optional[UID|str] ) -> Resources:
		"""
		Finds all recording resources. Optinally restricts the result to the provided UIDs.
		"""
		resources = Resources( *chain( *[self.find_resources_for( uid ) for uid in uids] ) ) if uids else self._activities.iter_resources()
		return Resources( *[r for r in resources if r.type in self._recording_types] )

	def find_summaries( self, *uids: Optional[UID|str] ) -> Resources:
		"""
		Finds all summary resources. Optinally restricts the result to the provided UIDs.
		"""
		resources = Resources( *chain( *[self.find_resources_for( uid ) for uid in uids] ) ) if uids else self._activities.iter_resources()
		return Resources( *[r for r in resources if r.type in self._summary_types] )

# ---- DB Operations ----

def status_db( ctx: ApplicationContext ) -> None:
	table = RichTable( box=box.MINIMAL, show_header=False, show_footer=False )
	table.add_row( 'activities', pp( len( ctx.db.activities ) ) )

	activity_map = {}
	for a in ctx.db.activities:
		if a.uid.classifier not in activity_map.keys():
			activity_map[a.uid.classifier] = 1
		else:
			activity_map[a.uid.classifier] = activity_map[a.uid.classifier] + 1

	for k in sorted( activity_map.keys() ):
		table.add_row( f' - {k}', pp( activity_map[k] ) )
	table.add_row( 'resources', pp( len( ctx.db.resources ) ) )

	ctx.console.print( table )

def maintain_db( ctx: ApplicationContext, maintenance: str, **kwargs ) -> None:
	if not maintenance:
		[ctx.console.print( f ) for f in migrate_db_functions( ctx )]
	else:
		migrate_db( ctx, maintenance, **kwargs )
