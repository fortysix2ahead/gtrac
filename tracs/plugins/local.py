from io import UnsupportedOperation
from logging import getLogger
from pathlib import Path
from shutil import copy2 as copy, move
from typing import Any, List, Optional, Tuple, Union
from urllib.parse import urlparse
from urllib.request import url2pathname
from uuid import uuid1

from fs.base import FS
from fs.copy import copy_file
from fs.osfs import OSFS
from fs.subfs import SubFS
from fs.zipfs import ZipFS

from config import ApplicationContext
from plugins.gpx import GPXImporter
from tracs.activity import Activity
from tracs.plugin import Plugin
from tracs.pluginmgr import service
from tracs.resources import Resource, Resources
from tracs.service import Service
from tracs.utils import abspath

log = getLogger( __name__ )

# plugin supporting local imports

SERVICE_NAME = 'local'
DISPLAY_NAME = 'Local'

class LocalActivity( Activity ):
	pass

@service
class Local( Service, Plugin ):

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

	def unified_import( self, ctx: ApplicationContext, force: bool = False, pretend: bool = False, **kwargs ) -> Tuple[FS, Resources]:
		root_fs = OSFS( '/' )
		import_path = f'imports/{self.name}_{str( uuid1() )[0:8]}'
		ctx.tmp_fs.makedir( 'imports', recreate=True )
		ctx.tmp_fs.makedir( import_path, recreate=True )
		tmp_fs = SubFS( ctx.tmp_fs, import_path )
		resources = Resources()

		classifier = kwargs.get( 'classifier', self.name )
		location = abspath( kwargs.get( 'location' ) )
		location_info = root_fs.getinfo( location )

		if location_info.is_dir:
			fs = OSFS( location )

		elif location_info.is_file and location_info.suffix == '.zip':
			fs = ZipFS( location )

		else:
			log.error( f'unsupported location: {location}' )
			raise UnsupportedOperation

		for path, dirs, files in fs.walk.walk( '/', filter=[ '*.gpx' ], exclude_dirs=[ '__MACOSX' ] ):
			for f in files:
				try:
					src_path = f'{path}/{f.name}'
					a = self._gpx_importer.load_as_activity( fs=fs, path=src_path )
					dst_path = f'{a.starttime.strftime( "%y%m%d%H%M%S" )}{f.suffix}'
					copy_file( fs, src_path, tmp_fs, dst_path ) # todo: avoid file collisions
					resources.extend( a.resources )
					log.debug( f'copy {fs}/{src_path} to {fs}/{dst_path}' )
				except AttributeError:
					log.error( f'unable to read GPX file from FS {fs}, path {path}/{f.name}' )

		return tmp_fs, resources
