
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from importlib import import_module
from importlib.resources import path as pkg_path
from logging import getLogger
from pathlib import Path
from typing import Any, Optional
from typing import List
from typing import Tuple

from appdirs import AppDirs
from confuse import Configuration
from confuse import Subview
from rich.console import Console
from rich.progress import Progress
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn

# string constants

APPNAME = 'tracs'
APPDIRS = AppDirs( appname=APPNAME )

BACKUP_DIRNAME = '.backup'
CACHE_DIRNAME = '.cache'
DB_DIRNAME = 'db'
DB_FILENAME = 'db.json'
LOG_DIRNAME = 'logs'
LOG_FILENAME = f'{APPNAME}.log'
OVERLAY_DIRNAME = 'overlay'
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

# application context

@dataclass
class ApplicationContext:

	instance: Any = field( default=None )

	config: Configuration = field( default=None )
	#config_default: Configuration = field( default=None )
	#config_user: Configuration = field( default=None )

	state: Configuration = field( default=None )
	#state_default: Configuration = field( default=None )
	#state_user: Configuration = field( default=None )

	# configuration
	cfg_dir: Path = field( default=None )
	cfg_file: Path = field( default=None )
	state_file: Path = field( default=None )

	# database
	db: Any = field( default=None )
	db_dir: Path = field( default=None )
	db_file: Path = field( default=None )

	meta: Any = field( default=None )

	lib_dir: Path = field( default=None )

	overlay_dir: Path = field( default=None )
	takeout_dir: Path = field( default=None )
	plugins_dir: List[Path] = field( default_factory=list )
	var_dir: Path = field( default=None )

	log_dir: Path = field( default=None )
	log_file: Path = field( default=None )

	force: bool = field( default=False )
	verbose: bool = field( default=False )
	debug: bool = field( default=False )
	pretend: bool = field( default=False )

	console: Console = field( default=cs )
	progress: Progress = field( default=None )
	task_id: Any = field( default=None )

	apptime: datetime = field( default=None )

	def __post_init__( self ):
		# directories depending on cfg_dir
		if self.cfg_dir:
			self.cfg_file = Path( self.cfg_dir, CONFIG_FILENAME ) if not self.cfg_file else self.cfg_file
			self.state_file = Path( self.cfg_dir, STATE_FILENAME ) if not self.state_file else self.state_file

			self.log_dir = Path( self.cfg_dir, LOG_DIRNAME ) if not self.log_dir else self.log_dir
			self.log_file = Path( self.log_dir, LOG_FILENAME ) if not self.log_file else self.log_file

		if self.lib_dir:
			self.db_dir = Path( self.lib_dir, DB_DIRNAME ) if not self.db_dir else self.db_dir

		# directories that depend on db_dir
		if self.db_dir:
			self.overlay_dir = Path( self.db_dir, OVERLAY_DIRNAME ) if not self.overlay_dir else self.overlay_dir
			self.takeout_dir = Path( self.db_dir, TAKEOUT_DIRNAME ) if not self.takeout_dir else self.takeout_dir
			self.var_dir = Path( self.db_dir, VAR_DIRNAME ) if not self.var_dir else self.var_dir

		# read internal config
		self.config = Configuration( APPNAME, __name__, read=False )
		with pkg_path( self.__module__, CONFIG_FILENAME ) as p:
			self.config.set_file( p )

		# read internal state
		self.state = Configuration( f'{APPNAME}.state', __name__, read=False )
		with pkg_path( self.__module__, STATE_FILENAME ) as p:
			self.state.set_file( p )

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
with pkg_path( import_module( NAMESPACE_CONFIG ), CONFIG_FILENAME ) as p:
	ApplicationConfig.set_file( p )
with pkg_path( import_module( NAMESPACE_CONFIG ), STATE_FILENAME ) as p:
	ApplicationState.set_file( p )

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
