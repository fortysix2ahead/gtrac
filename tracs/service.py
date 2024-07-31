
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timedelta
from inspect import getmembers
from logging import getLogger
from pathlib import Path
from typing import Any, cast, List, Optional, Tuple, Union

from dateutil.tz import UTC
from fs.base import FS
from fs.errors import ResourceNotFound
from fs.multifs import MultiFS
from fs.path import combine, dirname, frombase

from tracs.activity import Activity
from tracs.config import current_ctx
from tracs.db import ActivityDb
from tracs.plugin import Plugin
from tracs.registry import Registry
from tracs.resources import Resource
from tracs.uid import UID

log = getLogger( __name__ )

# ---- base class for a service ----

class Service( Plugin ):

	def __init__( self, *args, **kwargs ):
		super().__init__( *args, **kwargs )

		# paths + plugin filesystem area
		self._fs: FS = kwargs.get( 'fs' ) or ( self.ctx.plugin_fs( self.name ) if self.ctx else None )
		self._dbfs = kwargs.get( 'dbfs' ) or ( self.ctx.db_fs if self.ctx else None )
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

	@classmethod
	def default_path_for_id( cls, local_id: Union[int, str], base_path: Optional[str] = None, resource_path: Optional[str] = None, as_path: bool = False ) -> Union[Path, str]:
		local_id_rjust = str( local_id ).rjust( 3, '0' )
		path = f'{local_id_rjust[0]}/{local_id_rjust[1]}/{local_id_rjust[2]}/{local_id}'
		path = combine( base_path, path ) if base_path else path
		path = combine( path, resource_path ) if resource_path else path
		return Path( path ) if as_path else path

	@classmethod
	def path_for_uid( cls, uid: Union[UID, str], absolute: bool = False, as_path=True, ctx=None ) -> Union[Path, str]:
		"""
		Returns the relative path for a given uid.
		A service with the classifier of the uid has to exist, otherwise None will be returned.
		"""
		uid = UID( uid ) if isinstance( uid, str ) else uid
		ctx = ctx if ctx else current_ctx()
		try:
			service = ctx.registry.services.get( uid.classifier )
			return service.path_for_id( uid.local_id, service.name, uid.path, as_path=as_path )
		except AttributeError:
			return Service.default_path_for_id( uid.local_id, uid.classifier, uid.path, as_path=as_path )

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

	@classmethod
	def as_activity( cls, resource: Resource, registry: Registry = None, **kwargs ) -> Optional[Activity]:
		"""
		Loads a resource and transforms it into an activity by using the importer indicated by the resource type.
		"""
		ctx = current_ctx()
		fs, path = ctx.db_fs, Service.path_for_resource( resource, as_path=False )
		registry = registry if registry else ctx.registry
		return registry.importer_for( resource.type ).load_as_activity( path=path, fs=fs, **kwargs )

	@classmethod
	def as_activity_from( cls, resource: Resource, registry: Registry = None, **kwargs ) -> Optional[Activity]:
		"""
		Loads a resource to an activity in a 'lazy' manner, reusing the existing content of the resource.
		"""
		registry = registry if registry else current_ctx().registry
		return registry.importer_for( resource.type ).load_as_activity( resource=resource, **kwargs )

	# service methods

	# todo: set as_path to a default of False
	def path_for_id( self, local_id: Union[int, str], base_path: Optional[str] = None, resource_path: Optional[str] = None, as_path: bool = True ) -> Union[Path, str]:
		return Service.default_path_for_id( local_id, base_path, resource_path, as_path )

	def path_for( self, resource: Resource, ignore_overlay: bool = True, absolute: bool = True, omit_classifier: bool = False, as_path: bool = True ) -> Optional[Path]:
		"""
		Returns the path in the local file system where all artefacts of a provided activity are located.

		:param resource: resource for which the path shall be calculated
		:param ignore_overlay: if True ignores the overlay
		:param absolute: if True returns an absolute path
		:param omit_classifier: if True, the relative path will not include the leading name of the service
		:param as_path: if True, return the result as Path
		:return: path of the resource in the local file system
		"""
		uid = resource.uid_obj

		if uid.classifier != self.name:
			# this should not happen, if it does, something's wrong
			log.warning( f'called path_for() on service {self.name} for a foreign resource with UID {resource.uidpath}' )

		if omit_classifier and not absolute:
			path = self.path_for_id( uid.local_id, None, resource_path=uid.path, as_path=False )
		else:
			path = self.path_for_id( uid.local_id, uid.classifier, resource_path=uid.path, as_path=False )

		if absolute:
			try:
				path = self.fs.getsyspath( path )
			except (AttributeError, ResourceNotFound):
				path = f'/{path}' if not omit_classifier else f'{frombase( uid.classifier, path )}'

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

	# methods related to fetch()

	def fetch_summary_resources( self, skip: bool, force: bool, pretend: bool, **kwargs ) -> List[Union[Resource, int]]:
		if skip:
			summaries = self.ctx.db.summaries
		else:
			summaries = self.fetch( force=force, pretend=pretend, **kwargs )  # fetch all summary resources

		# sort summaries by uid so that progress bar in download looks better -> todo: improve progress bar later?
		return sorted( summaries, key=lambda r: r.uid )


	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Union[Resource, int]]:
		"""
		This method has to be implemented by a service class. It shall fetch information for
		activities from an external service and return a list of either summary resources or ids.
		This way it can be checked what activities exist and which identifier they have.

		:param force: flag to signal force execution
		:param pretend: pretend flag, do not persist anything
		:param kwargs: additional parameters
		:return: list of fetched summary resources
		"""
		return []

	def fetch_ids( self ) -> List[int]:
		return [ r.local_id for r in self.fetch( force=False, pretend=False ) ]

	# noinspection PyMethodMayBeStatic
	def filter_fetched( self, resources: List[Resource], *uids, **kwargs ) -> List[Resource]:
		# return [r for r in resources if r.uid in uids] if uids else resources
		return [r for r in resources if r.uid in uids]

	# methods related to download()

	def download( self, summary: Resource, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		"""
		Downloads related resources like GPX recordings based on a provided activity or summary resource.
		TODO: create a method for all services to ease implementation of subclasses.

		:param summary: summary resource
		:param force: flag force
		:param pretend: pretend flag
		:param kwargs: additional parameters
		:return: a list of downloaded resources
		"""
		return []

	def download_resource( self, resource: Resource, **kwargs ) -> Tuple[Any, int]:
		"""
		Downloads a single resource and returns the content + a status to signal that something has gone wrong.

		:param resource: resource to be downloaded
		:param kwargs: additional parameters
		:return: tuple containing the content + status
		"""
		pass

	def persist_resources( self, resources: List[Resource], force: bool, pretend: bool, **kwargs ) -> None:
		[ self.persist_resource( r, force, pretend, **kwargs ) for r in resources ]

	def persist_resource( self, resource: Resource, force: bool, pretend: bool, **kwargs ) -> None:
		path = self.path_for_resource( resource, as_path=False )
		if pretend:
			log.info( f'pretending to write resource {resource.uidpath}' )
			return

		if not path:
			log.debug( f'unable to calculate path for resource {resource.uidpath}' )
			return

		if self.dbfs.exists( path ) and not force:
			log.debug( f'not persisting resource {resource.uidpath}, path already exists: {path}' )
			return

		if not resource.content or not len( resource.content ) > 0:
			log.debug( f'not persisting resource {resource.uidpath} as content missing (0 bytes)' )
			return

		try:
			self.dbfs.makedirs( dirname( path ), recreate=True )
			self.dbfs.writebytes( path, resource.content )
			self.ctx.db.upsert_resources( resource )
		except TypeError:
			log.error( f'error writing resource data for resource {resource.uidpath}', exc_info=True )

	# noinspection PyMethodMayBeStatic
	def postprocess_summaries( self, resources: List[Resource], **kwargs ) -> List[Resource]:
		return resources

	# noinspection PyMethodMayBeStatic
	def postprocess_downloaded( self, resources: List[Resource], **kwargs ) -> List[Resource]:
		return resources

	def postprocess_resources( self, resources: List[Resource], **kwargs ) -> None:
		[ self.postprocess_resource( resource, **kwargs ) for resource in resources ]

	def postprocess_resource( self, resource: Resource = None, **kwargs ) -> None:
		pass

	# noinspection PyMethodMayBeStatic,PyUnresolvedReferences
	def create_activities( self, summary: Resource, resources: List[Resource], **kwargs ) -> List[Activity]:
		activities = [ Service.as_activity_from( summary ) ]
		now = datetime.now( UTC )
		for a in activities:
			a.metadata.created = now
		return activities

	# noinspection PyMethodMayBeStatic
	def postprocess_activities( self, activities: List[Activity], resources: List[Resource], **kwargs ) -> List[Activity]:
		"""
		Postprocesses activities after they have been created, by default nothing is done.

		:param activities: activities to postprocess
		:param resources: associated resources, belonging to the provided activities
		:return: postprocessed activities
		"""
		return activities

	def persist_activities( self, activities: List[Activity], force: bool, pretend: bool, **kwargs ) -> None:
		[ self._db.upsert_activity( a ) for a in activities ]

	def import_activities( self, force: bool = False, pretend: bool = False, **kwargs ):
		fetch_all = kwargs.get( 'fetch_all', False )
		first_year = kwargs.get( 'first_year', 2000 )
		days_range = kwargs.get( 'days_range', 90 )

		if fetch_all:
			range_from = datetime( first_year, 1, 1, tzinfo=UTC )
		else:
			range_from = datetime.utcnow().astimezone( UTC ) - timedelta( days = days_range )
		range_to = datetime.utcnow().astimezone( UTC ) + timedelta( days=1 )

		skip_fetch = kwargs.get( 'skip_fetch', False )
		skip_download = kwargs.get( 'skip_download', False )

		if not self.login():
			return

		# start fetch task
		self.ctx.start( f'fetching activity data from {self.display_name}, ()' )

		# fetch summaries
		summaries = self.fetch_summary_resources( skip_fetch, force, pretend, **{ 'range_from': range_from, 'range_to': range_to, **kwargs } )
		summaries = self.postprocess_summaries( summaries, **kwargs )  # post process summaries

		# filter out summaries that are already known
		if not force:
			summaries = [s for s in summaries if not self.ctx.db.contains_resource( s.uid, s.path )]

		# mark task as done
		self.ctx.complete( 'done' )

		# download resources

		self.ctx.start( f'downloading activity data from {self.display_name}', len( summaries ) )

		while summaries and ( summary := summaries.pop() ):
			# download resources for summary
			self.ctx.advance( f'{summary.uid}' )

			downloaded_resources = self.download( summary=summary, force=force, pretend=pretend, **kwargs ) if not skip_download else []
			downloaded_resources = self.postprocess_downloaded( downloaded_resources, **kwargs )  # post process
			resources = [summary, *downloaded_resources]

			# persist all resources
			self.persist_resources( resources, force=force, pretend=pretend, **kwargs )

			# create activity/activities from downloaded resources
			activities = self.create_activities( summary=summary, resources=resources, **kwargs )
			activities = self.postprocess_activities( activities, resources, **kwargs )

			# persist activities
			self.persist_activities( activities, force=force, pretend=pretend, **kwargs )

		# mark download task as done
		self._db.commit()
		self.ctx.complete( 'done' )

# helper functions

def path_for_id( local_id: Union[int, str], base_path: Optional[Path] = None, resource_path: Optional[Path] = None ) -> Path:
	local_id_rjust = str( local_id ).rjust( 3, '0' )
	path = Path( f'{local_id_rjust[0]}/{local_id_rjust[1]}/{local_id_rjust[2]}/{local_id}' )
	path = Path( base_path, path ) if base_path else path
	path = Path( path, resource_path ) if resource_path else path
	return path
