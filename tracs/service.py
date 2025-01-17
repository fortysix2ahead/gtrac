
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timedelta
from inspect import getmembers
from logging import getLogger
from pathlib import Path
from typing import Any, cast, List, Optional, Tuple, Union

from arrow import utcnow
from dateutil.tz import UTC
from fs.base import FS
from fs.copy import copy_file
from fs.errors import NoSysPath, ResourceNotFound
from fs.multifs import MultiFS
from fs.osfs import OSFS
from fs.path import basename, combine, dirname, isabs, join, parts, split

from tracs.activity import Activity, Activities
from tracs.config import current_ctx, DB_DIRNAME
from tracs.db import ActivityDb
from tracs.plugin import Plugin
from tracs.resources import Resource, Resources
from tracs.uid import UID

log = getLogger( __name__ )

# ---- base class for a service ----

class Service( Plugin ):

	def __init__( self, *args, **kwargs ):
		super().__init__( *args, **kwargs )

		# paths + plugin filesystem area
		self._fs: FS = kwargs.get( 'fs' ) or ( self.ctx.plugin_fs( self.name ) if self.ctx else None )
		self._dbfs = kwargs.get( 'dbfs' ) or ( self.ctx.db_fs if self.ctx else None )
		self._tmpfs = kwargs.get( 'tmp_fs' ) or ( self.ctx.tmp_fs if self.ctx else None )
		self._rootfs = OSFS( '/' )
		self._base_url = kwargs.get( 'base_url' )
		self._logged_in: bool = False

		# set service properties from kwargs, if a setter exists # todo: is this really needed?
		for p in getmembers( self.__class__, lambda p: type( p ) is property and p.fset is not None ):
			if p[0] in kwargs.keys() and not p[0].startswith( '_' ):
				setattr( self, p[0], kwargs.get( p[0] ) )

		log.debug( f'service instance {self._name} created with fs = {self._fs}' )

	# properties

	@property
	def logged_in( self ) -> bool:
		return self._logged_in

	@property
	def base_path( self ) -> Path:
		return Path( self.fs.getsyspath( '/' ) )

	@property
	def overlay_path( self ) -> Path:
		return Path( self.fs.getsyspath( '/' ) ) # todo: this is not yet correct

	@property
	def base_url( self ) -> str:
		return self._base_url

	@property # todo: remove later for self.db
	def _db( self ) -> ActivityDb:
		return self.db

	# fs properties (read-only)

	@property
	def fs( self ) -> FS:
		return self._fs

	@property
	def dbfs( self ) -> FS:
		return self._dbfs

	@property
	def base_fs( self ) -> FS:
		return cast( MultiFS, self._fs ).get_fs( 'base' )

	@property
	def overlay_fs( self ) -> FS:
		return cast( MultiFS, self._fs ).get_fs( 'overlay' )

	# class methods for helping with various things

	@staticmethod
	def default_path_for_id( local_id: Union[int, str], base_path: Optional[str] = None, resource_path: Optional[str] = None ) -> str:
		local_id_rjust = str( local_id ).rjust( 3, '0' )
		path = f'{local_id_rjust[0]}/{local_id_rjust[1]}/{local_id_rjust[2]}/{local_id}'
		path = combine( base_path, path ) if base_path else path
		path = combine( path, resource_path ) if resource_path else path
		return path

	@classmethod
	def path_for_uid( cls, uid: Union[UID, str], absolute: bool = False, as_path=False, ctx=None ) -> Union[Path, str]:
		"""
		Returns the relative path for a given uid.
		A service with the classifier of the uid has to exist, otherwise None will be returned.
		"""
		uid = UID( uid ) if isinstance( uid, str ) else uid
		ctx = ctx if ctx else current_ctx()

		try:
			service = ctx.registry.services.get( uid.classifier )
			path = service.path_for_id( uid.local_id, service.name, uid.path )
		except AttributeError:
			path = Service.default_path_for_id( uid.local_id, uid.classifier, uid.path )

		return Path( path ) if as_path else path

	@classmethod
	def path_for_resource( cls, resource: Resource, absolute: bool = True, as_path: bool = True, ignore_overlay: bool = True ) -> Union[Path, str]:
		try:
			service = current_ctx().registry.services.get( resource.classifier )
			return service.path_for( resource=resource, absolute=absolute, as_path=as_path, ignore_overlay=ignore_overlay )
		except AttributeError:
			log.error( f'unable to calculate resource path for {resource}', exc_info=True )

	@classmethod
	def url_for_uid( cls, uid: str ) -> Optional[str]:
		classifier, local_id = uid.split( ':', 1 )
		if service := current_ctx().registry.services.get( classifier ):
			return service.url_for( local_id=local_id )
		else:
			return None

	@staticmethod
	def as_activity( resource: Resource, **kwargs ) -> Activity:
		"""
		Loads a resource and transforms it into an activity by using the importer indicated by the resource type.
		"""
		Service.load_resources( None, resource )
		importer = kwargs.get( 'ctx', current_ctx() ).registry.importer_for( resource.type )
		activity = importer.load_as_activity( resource=resource )
		activity.metadata.created = utcnow().datetime
		activity.resources = Resources( resource )
		return activity

	@staticmethod
	def as_activity_from( resource: Resource, **kwargs ) -> Optional[Activity]:
		"""
		Loads a resource to an activity in a 'lazy' manner, reusing the existing content of the resource.
		"""
		registry = kwargs.get( 'registry', current_ctx().registry )
		return registry.importer_for( resource.type ).load_as_activity( resource=resource, **kwargs )

	@staticmethod
	def load_resources( activity: Optional[Activity] = None, *resources: Resource, **kwargs ):
		"""
		Loads the provided resources, either from the list or from the activity. This will only load the content, the activity will not be updated.

		:param activity: activity, which resources shall be loaded
		:param resources: list of resources to load
		:param kwargs: ctx: context to use, if omitted current_ctx() will be used
		:return:
		"""
		ctx = kwargs.get( 'ctx', current_ctx() )
		resources = activity.resources if activity else resources or []
		for r in resources:
			if importer := ctx.registry.importer_for( r.type ):
				importer.load( path=r.path, fs=ctx.db_fs, resource=r ) # todo: implement exception handling here

	# service methods

	def path_for_id( self, local_id: Union[int, str], base_path: Optional[str] = None, resource_path: Optional[str] = None, as_path: bool = False ) -> Union[Path, str]:
		path = Service.default_path_for_id( local_id, base_path, resource_path )
		return Path( path ) if as_path else path

	def path_for( self, resource: Resource, absolute: bool = False, omit_classifier: bool = False, ignore_overlay: bool = True, as_path: bool = False ) -> Optional[Union[Path, str]]:
		"""
		Returns the path in the local file system where all artefacts of a provided activity are located.

		:param resource: resource for which the path shall be calculated
		:param ignore_overlay: if True ignores the overlay
		:param absolute: if True returns an absolute path
		:param omit_classifier: if True, the relative path will not include the leading name of the service
		:param as_path: if True, return the result as Path
		:return: path of the resource in the local file system
		"""
		uid = resource.uid
		path = resource.path or resource.uid.path
		head, tail = split( path )

		if isabs( path ):
			return path

		if not head:
			path = self.path_for_id( uid.local_id, uid.classifier, resource_path=path, as_path=False )

		if omit_classifier and not absolute:
			path = join( *parts( path )[2:] )

		if absolute:
			try:
				path = self.dbfs.getsyspath( path )
			except (AttributeError, ResourceNotFound, NoSysPath ):
				path = f'/{DB_DIRNAME}/{path}'

		return Path( path ) if as_path else path

	def url_for( self, activity: Optional[Activity] = None, resource: Optional[Resource] = None, local_id: Optional[int] = None ) -> Optional[str]:
		url = None

		if local_id:
			url = self.url_for_id( local_id )
		elif resource and resource.classifier == self.name:
			url = self.url_for_resource_type( resource.local_id, resource.type )
		elif activity:
			try:
				uid = activity.as_uid()
				if uid.classifier == self.name:
					url = self.url_for_id( uid.local_id )
			except KeyError:
				pass

		return url

	@abstractmethod
	def url_for_id( self, local_id: Union[int, str] ) -> str:
		pass

	@abstractmethod
	def url_for_resource_type( self, local_id: Union[int, str], type: str ):
		pass

	# login method

	def login( self ) -> bool:
		pass

	def import_activities( self, force: bool = False, pretend: bool = False, **kwargs ) -> Activities:
		fetch_all = kwargs.get( 'fetch_all' ) or self.ctx.config['import'].fetch_all
		first_year = self.ctx.config['import'].first_year
		days_range = self.ctx.config['import'].range

		if fetch_all:
			range_from = datetime( first_year, 1, 1, tzinfo=UTC )
		else:
			range_from = datetime.now( UTC ) - timedelta( days = days_range )
		range_to = datetime.now( UTC ) + timedelta( days=1 )

		src_fs = kwargs.get( 'fs' )
		src_path = kwargs.get( 'path' )

		classifier = kwargs.get( 'classifier' ) or self.name
		type = kwargs.get( 'type' )

		skip_fetch = kwargs.get( 'skip_fetch', False )
		skip_download = kwargs.get( 'skip_download', False )

		dst_fs = self.ctx.import_fs()

		# actual import from local fs or remote
		if src_fs and self.supports_fs_import( src_fs, src_path ):
			log.debug( f'service {self.name} supports import from {src_fs}' )
			activities = self.import_from_fs( src_fs, dst_fs, path=src_path, classifier=classifier, type=type )

		elif self.supports_remote_import():
			activities = self.import_from_remote( dst_fs, range_from=range_from, range_to=range_to )

		else:
			activities = Activities()

		# post-process activities
		for a in activities:
			# move imported resources
			for r in a.resources:
				if force or not self.ctx.db_fs.exists( r.path ):
					try:
						self.ctx.db_fs.makedirs( dirname( r.path ), recreate=True )
						copy_file( dst_fs, r.path, self.ctx.db_fs, r.path, preserve_time=True )
						dst_fs.remove( r.path )
						# don't know why move_file fails, maybe a bug?
						# move_file( import_fs, r.path, ctx.db_fs, r.path, preserve_time=True )
						log.info( f'imported resource {UID( a.uid.classifier, a.uid.local_id, path=basename( r.path ) )}' )
					except ResourceNotFound:
						log.error( f'error importing from resource {UID( a.uid.classifier, a.uid.local_id, path=basename( r.path ) )}' )

				else:
					log.info( f'skipping import of resource {r}, file already exists, use option -f/--force to force overwrite' )

			# insert / upsert newly created activities
			if self.ctx.db.contains_activity( a.uid ):
				self.ctx.db.upsert( a )
			else:
				self.ctx.db.insert( a )

		# commit changes to db
		self.ctx.db.commit()

		# return imported activities
		return activities

	# noinspection PyMethodMayBeStatic
	def supports_fs_import( self, fs: FS | None, path: str | None ) -> bool:
		return False

	# noinspection PyMethodMayBeStatic
	def import_from_fs( self, src_fs: FS, dst_fs: FS, **kwargs ) -> Activities:
		return Activities()

	# noinspection PyMethodMayBeStatic
	def supports_remote_import( self ) -> bool:
		return False

# helper functions

def path_for_id( local_id: int|str, base_path: str = None, resource_path: str = None ) -> str:
	local_id_rjust = str( local_id ).rjust( 3, '0' )
	path = f'{local_id_rjust[0]}/{local_id_rjust[1]}/{local_id_rjust[2]}/{local_id}'
	path = f'{base_path}/{path}' if base_path else path
	path = f'{path}/{resource_path}' if resource_path else path
	return path

def path_for_date( date_id: Union[int, str, datetime] ) -> str:
	if isinstance( date_id, int ):
		date_id = str( date_id )
	elif isinstance( date_id, datetime ):
		date_id = date_id.strftime( "%y%m%d%H%M%S" )

	date_id = str( date_id ).rjust( 6, '0' )
	return f'{date_id[0:2]}/{date_id[2:4]}/{date_id[4:6]}/{date_id}'
