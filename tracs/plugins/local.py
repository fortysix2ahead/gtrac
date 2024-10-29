from io import UnsupportedOperation
from logging import getLogger
from pathlib import Path
from shutil import copy2 as copy, move
from typing import Any, List, Optional, Tuple, Union
from urllib.parse import urlparse
from urllib.request import url2pathname

from fs.base import FS
from fs.copy import copy_file
from fs.errors import ResourceNotFound
from fs.osfs import OSFS
from fs.path import dirname
from fs.subfs import SubFS
from fs.zipfs import ReadZipFS

from tracs.activity import Activities, Activity
from tracs.config import ApplicationContext
from tracs.errors import ResourceImportException
from tracs.pluginmgr import service
from tracs.plugins.gpx import GPXImporter
from tracs.resources import Resource
from tracs.service import path_for_date, Service
from tracs.uid import UID
from tracs.utils import abspath

log = getLogger( __name__ )

# plugin supporting local imports

SERVICE_NAME = 'local'
DISPLAY_NAME = 'Local'

class LocalActivity( Activity ):
	pass

@service
class Local( Service ):

	def __init__( self, **kwargs  ):
		super().__init__( name=SERVICE_NAME, display_name=DISPLAY_NAME, **kwargs )

		self._gpx_importer = GPXImporter()

	def path_for_id( self, local_id: Union[int, str], base_path: Optional[Path] ) -> Path:
		local_id = str( local_id )
		path = Path( local_id[0:2], local_id[2:4], local_id[4:6], local_id )
		return Path( base_path, path ) if base_path else path

	def url_for_id( self, local_id: Union[int, str] ) -> Optional[str]:
		return None

	def url_for_resource_type( self, local_id: Union[int, str], type: str ) -> Optional[str]:
		return None

	def login( self ) -> bool:
		return True

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		resources = []

		if (path := kwargs.get( 'path' )) and (overlay_id := kwargs.get( 'as_overlay', False )):
			ctx = kwargs.get( 'ctx' )
			resource = ctx.db.resources.get( doc_id = overlay_id )
			if resource:
				overlay_path = self.path_for( resource=resource, ignore_overlay=False )
				overlay_path.parent.mkdir( parents=True, exist_ok=True )
				if kwargs.get( 'move', False ):
					move( path, overlay_path )
				else:
					copy( path, overlay_path )

		if path := kwargs.get( 'path' ):
			if path.is_file():
				paths = [ path ]
			elif path.is_dir():
				paths = [ f for f in path.iterdir() ]
			else:
				paths = []

			for p in paths:
				activity = self.import_from_file( p )
				resource = activity.resources[0]
				resource.uid = f'{self.name}:{activity.starttime.strftime( "%y%m%d%H%M%S" )}'
				resource.path = f'{resource.local_id}.{resource.path.rsplit( ".", 1 )[1]}'
				resource.status = 200
				resources.append( resource )

		return resources

	# noinspection PyMethodMayBeStatic
	def postprocess( self, activity: Optional[Activity], resources: Optional[List[Resource]], **kwargs ) -> None:
		# todo: is this always correct?
		activity.uid = activity.resources[0].uid

	def persist_resource_data( self, activity: Activity, force: bool, pretend: bool, **kwargs ) -> None:
		if kwargs.get( 'move', False ):
			for r in activity.resources:
				src_path = Path( urlparse( url2pathname( r.source ) ).path )
				dest_path = self.path_for( resource=r )
				dest_path.parent.mkdir( parents=True, exist_ok=True )
				move( src_path, dest_path )
				r.dirty = True
		else:
			super().persist_resource_data( activity, force, pretend, **kwargs )

	# noinspection PyMethodMayBeStatic
	def import_from_file( self, path: Path ) -> Any:
		importers = Registry.importers_for_suffix( path.suffix[1:] )
		try:
			imported_data = None
			for i in importers:
				imported_data = i.load_as_activity( path=path )
				break
		except AttributeError:
			imported_data = None

		return imported_data

	def supports_import_fs( self, fs: FS|None, path: str|None ) -> bool:
		return True if fs else False

#	def unified_import( self, ctx: ApplicationContext, force: bool = False, pretend: bool = False, **kwargs ) -> Tuple[Activities, FS]:
	def import_from_fs( self, src_fs: FS, dst_fs: FS, **kwargs ) -> Activities:
		# classifier + optional location
		import_path = kwargs.get( 'path' )
		classifier = kwargs.get( 'classifier' ) or self.name

		filters = [ '*.gpx' ] # todo: support tcx as well
		if import_path:
			filters = [ import_path ]
		exclude_dirs = ['__MACOSX']

		# try:
		# 	location = abspath( kwargs.get( 'location' ) )
		# 	location_info = self._rootfs.getinfo( location )
		#
		# 	if location_info.is_dir:
		# 		fs, filters = OSFS( location ), [ '*.gpx' ]
		# 	elif location_info.is_file:
		# 		if location_info.suffix == '.zip':
		# 			fs, filters = ReadZipFS( location ), [ '*.gpx' ]
		# 		elif location_info.suffix in [ '.gpx' ]:
		# 			fs, filters = OSFS( dirname( location ) ), [ location_info.name ]
		# 		else:
		# 			raise UnsupportedOperation
		# 	else:
		# 		raise UnsupportedOperation
		#
		# except (ResourceNotFound, FileNotFoundError):
		# 	log.error( f'unsupported location: {location}' )
		# 	raise UnsupportedOperation

		activities = Activities() # list of imported activities

		for path, dirs, files in src_fs.walk.walk( '/', filter=filters, exclude_dirs=['__MACOSX'] ):
			for f in files:
				try:
					src_path = f'{path}/{f.name}'
					activity = self._gpx_importer.load_as_activity( fs=src_fs, path=src_path )
					activity.uid = UID( classifier, int( activity.starttime.strftime( "%y%m%d%H%M%S" ) ) )
					dst_path = f'{classifier}/{path_for_date( activity.starttime )}/{activity.starttime.strftime( "%y%m%d%H%M%S" )}{f.suffix}'

					if self.ctx.force or not self.db.contains_resource( activity.uid, dst_path ):
						dst_fs.makedirs( dirname( dst_path ), recreate=True )
						copy_file( src_fs, src_path, dst_fs, dst_path, preserve_time=True ) # todo: avoid file collisions
						log.debug( f'copy {src_fs}/{src_path} to {dst_fs}/{dst_path}' )

						resource = activity.resources.first()
						resource.path = dst_path
						# source URL is better than before, but maybe not final
						resource.source = src_fs.geturl( src_path, purpose='fs' ) if isinstance( src_fs, ReadZipFS ) else src_fs.geturl( src_path, purpose='download' )
						# don't need to set the resource uid as activity uid is set
						# resource.uid = UID( classifier, int( activity.starttime.strftime( "%y%m%d%H%M%S" ) ) )
						resource.unload()
						activities.append( activity )

					else:
						log.info( f'skipping import of {src_fs}/{src_path}, resource already exists' )

				except (AttributeError, ResourceImportException):
					log.error( f'unable to read GPX file from FS {src_fs}, path {path}/{f.name}' )

		return activities
