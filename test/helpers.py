
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from json import load as load_json
from pathlib import Path
from shutil import copy
from shutil import copytree

from importlib.resources import path
from shutil import rmtree
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from pytest import mark
from tinydb.table import Document

from tracs.activity import Activity
from tracs.config import ApplicationContext
from tracs.config import CONFIG_FILENAME
from tracs.config import DB_DIRNAME
from tracs.config import STATE_FILENAME
from tracs.db import ActivityDb
from tracs.plugins.gpx import GPX_TYPE
from tracs.resources import Resource
from tracs.service import Service

DATABASES = 'databases'
LIBRARIES = 'libraries'
VAR = 'var'
VAR_RUN = 'var/run'

@dataclass
class DbPath:

	parent: Path = field()
	activities: Path = field( default=None )
	metadata: Path = field( default=None )
	resources: Path = field( default=None )
	schema: Path = field( default=None )

	def __post_init__( self ):
		if self.parent:
			self.activities = Path( self.parent, 'activities.json' )
			self.metadata = Path( self.parent, 'metadata.json' )
			self.resources = Path( self.parent, 'resources.json' )
			self.schema = Path( self.parent, 'schema.json' )

class Mock( Service ):

	def __init__( self, **kwargs ):
		super().__init__( name='mock', display_name='Mock', **kwargs )

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		return [
			Resource( uid='mock:1001', path='1001.json', text='{}', type='application/mock+json' ),
			Resource( uid='mock:1002', path='1002.json', text='{}', type='application/mock+json' ),
			Resource( uid='mock:1003', path='1003.json', text='{}', type='application/mock+json' ),
		]

	def download( self, summary: Resource = None, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		return [Resource(
			uid=summary.uid,
			path=f'{summary.local_id}.gpx',
			text=gpx_resource,
			type=GPX_TYPE
		)]

	def url_for_id( self, local_id: Union[int, str] ) -> str:
		pass

	def url_for_resource_type( self, local_id: Union[int, str], type: str ):
		pass

	def setup( self, ctx: ApplicationContext ) -> None:
		pass

def prepare_environment( cfg_name: str = None, lib_name: str = None, db_name: str = None ) -> Tuple[Path, Path]:
	run_dir = _run_path()
	run_dir = Path( run_dir, f'{datetime.now().strftime( "%y%m%d_%H%M%S_%f" )}' )
	run_dir.mkdir()
	dot_dir = Path( run_dir, '.tracs' )
	dot_dir.mkdir()

	if cfg_name:
		cfg_path = get_config_path( cfg_name )
		copy( Path( cfg_path, 'config.yaml' ), run_dir )
		copy( Path( cfg_path, 'state.yaml' ), run_dir )

	if lib_name:
		# lib_path = get_lib_path( lib_name )
		lib_path = 'test'

	if db_name:
		db_path = get_db_path( db_name )
		copy( Path( db_path ), Path( dot_dir, 'db.json' ) )

	cfg_path = run_dir
	lib_path = run_dir

	return cfg_path, lib_path

def prepare_context( cfg_name: str, lib_name: str ) -> ApplicationContext:
	with path( 'test', '__init__.py' ) as test_path:
		cfg_path = var_run_path()
		lib_path = None

		if cfg_name:
			cfg_src_path = Path( test_path.parent, 'configurations', cfg_name )
			try:
				copy( Path( cfg_src_path, CONFIG_FILENAME ), cfg_path )
			except FileNotFoundError as error:
				pass

			try:
				copy( Path( cfg_src_path, STATE_FILENAME ), cfg_path )
			except FileNotFoundError as error:
				pass

		if lib_name:
			lib_src_path = Path( test_path.parent, 'libraries', lib_name )
			lib_path = Path( cfg_path )
			copytree( lib_src_path, Path( lib_path, DB_DIRNAME ) )

		return ApplicationContext( cfg_dir=cfg_path, lib_dir=lib_path, db=ActivityDb( path=lib_path ) )

def get_config_path( name: str, writable: bool = False ) -> Path:
	with path( 'test', '__init__.py' ) as test_path:
		config_path = Path( test_path.parent, 'configurations', name )
		if writable:
			writable_config_path = Path( _run_path(), f'cfg_{name}-{datetime.now().strftime( "%H%M%S_%f" )}' )
			copytree( config_path, writable_config_path )
			config_path = writable_config_path
		return config_path

def get_db_path( template_name: str = None, library_name: str = None, read_only: bool = False ) -> DbPath:
	"""
	Creates/returns an existing db and returns a tuple consisting of [parent_path, db_path, meta_path]

	:param template_name: template db name
	:return: Tuple of [parent_path, db_path, meta_path]
	"""
	with path( 'test', '__init__.py' ) as p:
		if template_name:
			db_path = DbPath( parent = Path( p.parent, DATABASES, template_name ) )
		elif library_name:
			db_path = DbPath( parent = Path( p.parent, LIBRARIES, library_name ) )

		if read_only:
			return db_path
		else:
			dest_path = var_run_path()
			dest_path.mkdir( exist_ok=True )
			copytree( db_path.parent, dest_path, dirs_exist_ok=True )
			return DbPath( dest_path )

def get_db( template: str = None, read_only: bool = False ) -> Optional[ActivityDb]:
	"""
	Returns an in-memory db initialized from the provided template db.

	:param template: template db or None
	:param read_only: read_only flag
	:return: db
	"""
	db_path = get_db_path( template_name=template, read_only=read_only )
	return ActivityDb( path=db_path.parent, read_only=read_only )

def get_inmemory_db( template: str = None, library: str = None ) -> Optional[ActivityDb]:
	"""
	Returns an in-memory db initialized from the provided template db.

	:param template: template db or None
	:param library: optional lib name
	:return: in-memory db
	"""
	if library:
		db_path = get_db_path( library_name=library, writable=False )
	elif template:
		db_path = get_db_path( template_name=template, writable=False )
	else:
		return None

	return ActivityDb( path=db_path.parent, pretend=True )

def get_file_db( template: str = None, library: str = None, writable = False ) -> ActivityDb:
	"""
	Returns a file-based db, based on the provided template.

	:param template:
	:param library:
	:param writable: if the db shall be writable or not
	:return: file-based db
	"""
	if library:
		db_path = get_db_path( library_name=library, writable=writable )
	else:
		db_path = get_db_path( template_name=template, writable=writable )

	return ActivityDb( path=db_path.parent, pretend=not writable )

def get_db_as_json( db_name: str ) -> Dict:
	parent_path, db_path, meta_path = get_db_path( db_name, writable=False )
	return load_json( open( db_path, 'r', encoding='utf8' ) )

def get_file_as_json( rel_path: str ) -> Dict:
	json_path = get_file_path( rel_path )
	return load_json( open( json_path, 'r', encoding='utf8' ) )

def get_file_path( rel_path: str ) -> Path:
	"""
	Provides a path relative to $PROJECT_DIR/test.

	:param rel_path: relative path
	:return: path relative to the /var/run directory
	"""
	with path( 'test', '__init__.py' ) as test_path:
		return Path( test_path.parent, rel_path )

def get_var_path( rel_path: str ) -> Path:
	"""
	Provides a path relative to $PROJECT_DIR/var.

	:param rel_path: relative path
	:return: path relative to the var directory
	"""
	with path( 'test', '__init__.py' ) as test_path:
		return Path( test_path.parent.parent, VAR, rel_path )

def get_var_run_path( rel_path: str ) -> Path:
	"""
	Provides a path relative to $PROJECT_DIR/var/run.

	:param rel_path: relative path
	:return: path relative to the var/run directory
	"""
	with path( 'test', '__init__.py' ) as test_path:
		return Path( test_path.parent.parent, VAR_RUN, rel_path )

def var_run_path( file_name = None ) -> Path:
	"""
	Creates a new directory/file in var/run directory. If the file_name is missing, the directory will be created and
	returned, otherwise only the file path will be returned and the parent dir will be created.

	:param file_name: file name
	:return: path
	"""
	with path( 'test', '__init__.py' ) as test_pkg_path:
		if file_name:
			run_path = Path( test_pkg_path.parent.parent, VAR_RUN, f'{datetime.now().strftime( "%H%M%S_%f" )}', file_name )
			run_path.parent.mkdir( parents=True, exist_ok=True )
		else:
			run_path = Path( test_pkg_path.parent.parent, VAR_RUN, f'{datetime.now().strftime( "%H%M%S_%f" )}' )
			run_path.mkdir( parents=True, exist_ok=True )
		return run_path

def cleanup( run_path: Path = None ) -> None:
	if run_path and run_path.parent.name == 'run' and run_path.parent.parent.name == 'var': # sanity check: only remove when in test/var/run
		rmtree( run_path, ignore_errors=True )

def ids( doc_list: [Document] ) -> []:
	return [a.doc_id for a in doc_list]

skip_live = mark.skipif(
	not ( get_var_path( 'config_live.yaml' ).exists() and get_var_path( 'state_live.yaml' ).exists() ), reason="live test not enabled as configuration is missing"
)

# mock gpx resource

gpx_resource = '''
<?xml version="1.0" encoding="UTF-8"?>
<gpx xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"
    xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2" version="1.1" creator="Pocket Earth v2.8"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns="http://www.topografix.com/GPX/1/1">
    <metadata>
        <name>Skaftafell - Vatnajökull</name>
        <link href="http://www.geomagik.com">
            <text>GeoMagik LLC</text>
        </link>
        <time>2015-08-02T12:16:20Z</time>
    </metadata>
    <trk>
        <name>Skaftafell - Vatnajökull</name>
        <trkseg>
            <trkpt lat="64.0162580" lon="-16.9656560">
                <ele>93.00</ele>
                <time>2015-07-27T17:40:56Z</time>
            </trkpt>
            <trkpt lat="64.0162390" lon="-16.9656320">
                <ele>93.00</ele>
                <time>2015-07-27T17:40:57Z</time>
            </trkpt>
            <trkpt lat="64.0162460" lon="-16.9656300">
                <ele>94.00</ele>
                <time>2015-07-27T17:40:58Z</time>
            </trkpt>
        </trkseg>
    </trk>
</gpx>
'''
