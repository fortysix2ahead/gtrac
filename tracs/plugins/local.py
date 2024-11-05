from logging import getLogger
from pathlib import Path
from typing import Optional, Union

from fs.base import FS
from fs.copy import copy_file
from fs.path import dirname, isparent, relativefrom
from fs.zipfs import ReadZipFS

from tracs.activity import Activities, Activity
from tracs.errors import ResourceImportException
from tracs.pluginmgr import service
from tracs.plugins.gpx import GPXImporter
from tracs.service import path_for_date, Service
from tracs.uid import UID

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

	def supports_fs_import( self, fs: FS | None, path: str | None ) -> bool:
		return True if fs else False

	def import_from_fs( self, src_fs: FS, dst_fs: FS, **kwargs ) -> Activities:
		# classifier + optional location
		import_path = kwargs.get( 'path' )
		classifier = kwargs.get( 'classifier' ) or self.name

		filters, max_depth = [ '*.gpx' ], 0 # todo: support tcx as well
		if import_path:
			filters, max_depth = [ import_path ], 1
		exclude_dirs = ['__MACOSX']

		activities = Activities() # list of imported activities

		for path, dirs, files in src_fs.walk.walk( '/', filter=filters, exclude_dirs=exclude_dirs, max_depth=max_depth ):
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
						# todo: support gzip
						if isinstance( src_fs, ReadZipFS ):
							resource.source = src_fs.geturl( src_path, purpose='fs' )
						else:
							if isparent( ld := self.ctx.lib_fs.getsyspath( '/' ), sp := src_fs.getsyspath( src_path ) ):
								resource.source = relativefrom( ld, sp )
							else:
								resource.source = src_fs.geturl( src_path, purpose='download' )

						# don't need to set the resource uid as activity uid is set
						# resource.uid = UID( classifier, int( activity.starttime.strftime( "%y%m%d%H%M%S" ) ) )
						resource.unload()
						activities.append( activity )

					else:
						log.info( f'skipping import of {src_fs}/{src_path}, resource already exists' )

				except (AttributeError, ResourceImportException):
					log.error( f'unable to read GPX file from FS {src_fs}, path {path}/{f.name}', exc_info=True )

		return activities
