
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from importlib.resources import path as pkg_path
from logging import getLogger
from pathlib import Path
from typing import Any, Optional
from typing import List
from typing import Tuple

from appdirs import AppDirs
from confuse import Configuration
from confuse import Subview
from fs.base import FS
from fs.osfs import OSFS
from rich.console import Console
from rich.progress import Progress
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn

# string constants

APPNAME = 'tracs'
APP_PKG_NAME = 'tracs'
APPDIRS = AppDirs( appname=APPNAME )

BACKUP_DIRNAME = '.backup'
CACHE_DIRNAME = '.cache'
DB_DIRNAME = 'db'
DB_FILENAME = 'db.json'
LOG_DIRNAME = 'logs'
LOG_FILENAME = f'{APPNAME}.log'
OVERLAY_DIRNAME = 'overlay'
RESOURCES_DIRNAME = 'resources'
TAKEOUT_DIRNAME = 'takeouts'
TMP_DIRNAME = '.tmp'
VAR_DIRNAME = 'var'

CONFIG_FILENAME = 'config.yaml'
STATE_FILENAME = 'state.yaml'

DEFAULT_CFG_DIR = Path( APPDIRS.user_config_dir )
DEFAULT_DB_DIR = Path( DEFAULT_CFG_DIR, DB_DIRNAME )

TABLE_NAME_DEFAULT = '_default'
TABLE_NAME_ACTIVITIES = 'activities'

CLASSIFIER = 'classifier'
CLASSIFIERS = 'classifiers'

KEY_CLASSIFER = 'classifier'
KEY_GROUP = 'group'
KEY_GROUPS = 'groups'
KEY_LAST_DOWNLOAD = 'last_download'
KEY_LAST_FETCH = 'last_fetch'
KEY_METADATA = 'metadata'
KEY_PARTS = 'parts'
KEY_PLUGINS = 'plugins'
KEY_SERVICE = KEY_CLASSIFER
KEY_RAW = 'raw'
KEY_RESOURCES = 'resources'
KEY_VERSION = 'version'

NAMESPACE_BASE = APPNAME
NAMESPACE_CONFIG = f'{NAMESPACE_BASE}.config'
NAMESPACE_PLUGINS = f'{NAMESPACE_BASE}.plugins'
NAMESPACE_SERVICES = f'{NAMESPACE_BASE}.services'

# default logger + console

log = getLogger( __name__ )
cs = Console( tab_size=2 )

def default_resources_path() -> Path:
	with pkg_path( APP_PKG_NAME, f'{RESOURCES_DIRNAME}' ) as path:
		return path

# application context

@dataclass
class ApplicationContext:

	# configuration fields which can be set externally
	config_dir: Optional[str] = field( default=None )
	lib_dir: Optional[str] = field( default=None )

	# global configuration flags, can be set externally
	force: Optional[bool] = field( default=None )
	verbose: Optional[bool] = field( default=None )
	debug: Optional[bool] = field( default=None )
	pretend: Optional[bool] = field( default=None )

	# everything below is calculated

	# filesystems
	config_fs: Optional[FS] = field( default=None )
	lib_fs: Optional[FS] = field( default=None )

	# files and directories
	default_resources_dir: Path = field( default=default_resources_path() )
	default_config_file: Path = field( default=Path( default_resources_path(), CONFIG_FILENAME ) )
	default_state_file: Path = field( default=Path( default_resources_path(), STATE_FILENAME ) )

	config_file: Path = field( default=CONFIG_FILENAME )
	state_file: Path = field( default=STATE_FILENAME )

	log_dir: Path = field( default=LOG_DIRNAME )
	log_file: Path = field( default=f'{LOG_DIRNAME}/{LOG_FILENAME}' )
	overlay_dir: Path = field( default=OVERLAY_DIRNAME )
	takeout_dir: Path = field( default=TAKEOUT_DIRNAME )
	var_dir: Path = field( default=VAR_DIRNAME )

	# database
	db: Any = field( default=None )
	db_dir: Path = field( default=DB_DIRNAME )

	instance: Any = field( default=None )
	config: Configuration = field( default=Configuration( APPNAME, __name__, read=False ) )
	state: Configuration = field( default=Configuration( f'{APPNAME}.state', __name__, read=False ) )
	meta: Any = field( default=None )

	plugins_dir: List[Path] = field( default_factory=list )

	console: Console = field( default=cs )
	progress: Progress = field( default=None )
	task_id: Any = field( default=None )

	apptime: datetime = field( default=None )

	def __post_init__( self ):
		# setup config fs
		if not self.config_dir:
			self.config_dir = APPDIRS.user_config_dir
		self.config_fs = OSFS( root_path=self.config_dir, create=True )

		# load default configuration/state
		self.config.set_file( self.default_config_file )
		if self.config_fs.exists( str( self.config_file ) ):
			self.config.set_file( self.config_fs.getsyspath( str( self.config_file ) ) )

		self.state.set_file( self.default_state_file )
		if self.config_fs.exists( str( self.state_file ) ):
			self.state.set_file( self.config_fs.getsyspath( str( self.state_file ) ) )

		# evaluate cmdline configuration flags
		self.debug = self.debug if self.debug is not None else self.config['debug'].get()
		self.verbose = self.verbose if self.verbose is not None else self.config['verbose'].get()
		self.force = self.force if self.force is not None else self.config['force'].get()
		self.pretend = self.pretend if self.pretend is not None else self.config['pretend'].get()

		# update configuration as well
		self.config['debug'] = self.debug
		self.config['verbose'] = self.verbose
		self.config['force'] = self.force
		self.config['pretend'] = self.pretend

		# setup library fs, if not provided, use config_dirf
		if not self.lib_dir and not self.config['library'].get():
			self.lib_dir = self.config_dir
			self.lib_fs = self.config_fs
			self.config['library'] = self.lib_dir
		else:
			if not self.lib_dir:
				self.lib_dir = self.config['library'].get()
			else:
				self.config['library'] = self.lib_dir
			self.lib_fs = OSFS( root_path=self.lib_dir, create=True )

		# create directories depending on config_dir
		self.config_fs.makedir( str( self.log_dir ), recreate=True )

		# create directories depending on log_dir
		self.lib_fs.makedir( str( self.db_dir ), recreate=True )
		self.lib_fs.makedir( str( self.overlay_dir ), recreate=True )
		self.lib_fs.makedir( str( self.takeout_dir ), recreate=True )
		self.lib_fs.makedir( str( self.var_dir ), recreate=True )

	@property
	def db_dir_path( self ) -> Path:
		return Path( self.lib_fs.getsyspath( str( self.db_dir ) ) )

	@property
	def db_overlay_path( self ) -> Path:
		return Path( self.lib_fs.getsyspath( str( self.overlay_dir ) ) )

	@property
	def lib_dir_path( self ) -> Path:
		return Path( self.lib_fs.getsyspath( '/' ) )

	@property
	def log_file_path( self ) -> Path:
		return Path( self.config_fs.getsyspath( str( self.log_file ) ) )

	# path helpers

	def db_dir_for( self, service_name: str ) -> Path:
		return Path( self.db_dir, service_name )

	def pp( self, *objects ):
		self.console.print( *objects )

	def ppx( self ):
		self.console.print_exception()

	def start( self, description: str = '', total = None ):
		if self.verbose:
			if description:
				self.pp( description )
		else:
			# create progress and start as start/stop/reuse does not seem to work
			self.progress = Progress( *Progress.get_default_columns(), TextColumn( '/' ), TimeElapsedColumn(), TextColumn( "{task.fields[msg]}" ), console=self.console )
			self.progress.start()
			self.task_id = self.progress.add_task( description=description, total=total, msg='' )

	def total( self, total = None ):
		self.progress.update( task_id=self.task_id, total=total )

	def advance( self, msg: str = None, advance: float = 1 ):
		if self.verbose:
			self.pp( msg )
		else:
			self.progress.update( task_id=self.task_id, advance=advance, msg=msg )

	def complete( self, msg: str = None ):
		if self.verbose:
			if msg:
				self.pp( msg )
		else:
			self.progress.update( task_id=self.task_id, advance=1, msg='' if msg is None else msg )
			self.progress.stop()

	def timeit( self, message: Optional[str] = None, skip_print: bool = False ):
		if not self.apptime:
			self.apptime = datetime.now()
		else:
			diff = datetime.now() - self.apptime
			if not skip_print:
				if message:
					self.console.print(f'{message}: {diff}')
				else:
					self.console.print( f'{diff}' )
			self.apptime = datetime.now()

	def dump_config_state( self ) -> None:
		self.dump_config()
		self.dump_state()

	def dump_config( self ) -> None:
		if not self.pretend:
			with open( self.cfg_file, 'w+' ) as cf:
				#cf.write( dump_yaml( load_yaml( self._cfg.dump( full=True ), Loader=FullLoader ), sort_keys=True ) )
				cf.write( self.config.dump( full=True ) )
		else:
			log.info( f'pretending to write config file to {self.cfg_file}' )

	def dump_state( self ) -> None:
		if not self.pretend:
			with open( self.state_file, 'w+' ) as sf:
				#sf.write( dump_yaml( load_yaml( self._state.dump( full=True ), Loader=FullLoader ), sort_keys=True ) )
				sf.write( self.state.dump( full=True ) )
		else:
			log.info( f'pretending to write state file to {self.state_file}' )

ApplicationConfig = Configuration( APPNAME, __name__, read=False )
ApplicationState = Configuration( f'{APPNAME}-state', __name__, read=False )

APP_CFG = ApplicationConfig
APP_STATE = ApplicationState

console = cs # to be removed by cs from above

# load defaults from internal package
#with pkg_path( import_module( NAMESPACE_CONFIG ), CONFIG_FILENAME ) as p:
#	ApplicationConfig.set_file( p )
#with pkg_path( import_module( NAMESPACE_CONFIG ), STATE_FILENAME ) as p:
#	ApplicationState.set_file( p )

def plugin_config_state( plugin: str ) -> Tuple[Subview, Subview]:
	return ApplicationConfig[KEY_PLUGINS][plugin], ApplicationState[KEY_PLUGINS][plugin]

# todo: to be replaced by application context
class GlobalConfig:

	app = None
	db = None
	cfg: Configuration = APP_CFG
	state: Configuration = APP_STATE

	cfg_dir: Path = None
	db_dir: Path = None
	db_file: Path = None
	lib_dir: Path = None
