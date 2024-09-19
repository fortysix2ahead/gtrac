
from __future__ import annotations

from datetime import datetime
from importlib.resources import path as pkg_path
from logging import getLogger
from os.path import abspath, dirname, expanduser, expandvars, isdir, isfile, split
from pathlib import Path
from typing import Any, cast, Dict, Optional, Tuple

from attrs import define, field
from dateutil.tz import tzlocal
from dynaconf import Dynaconf as Configuration
from dynaconf.utils.boxing import DynaBox
from dynaconf.vendor.box.exceptions import BoxKeyError
from fs.base import FS
from fs.errors import NoSysPath
from fs.multifs import MultiFS
from fs.osfs import OSFS
from fs.subfs import SubFS
from platformdirs import user_config_dir
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from yaml import safe_dump

# string constants

APPNAME = 'tracs'
APP_PKG_NAME = 'tracs'
PLUGINS_PKG_NAME = 'plugins'

BACKUP_DIRNAME = 'backup'
CACHE_DIRNAME = 'cache'
DB_DIRNAME = 'db'
DB_FILENAME = 'db.json'
IMPORT_DIRNAME = 'imports'
LOG_DIRNAME = 'logs'
LOG_FILENAME = f'{APPNAME}.log'
OVERLAY_DIRNAME = 'overlay'
RESOURCES_DIRNAME = 'resources'
TAKEOUT_DIRNAME = 'takeouts'
TMP_DIRNAME = 'tmp'
VAR_DIRNAME = 'var'

CONFIG_FILENAME = 'config.yaml'
STATE_FILENAME = 'state.yaml'
DEFAULT_CONFIG_FILENAME = 'defaults/config.yaml'
DEFAULT_STATE_FILENAME = 'defaults/state.yaml'

EXTRA_KWARGS = ['debug', 'force', 'verbose', 'pretend']

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

# one´console, reuse this in application context -> this needs to be consolidated
CONSOLE = Console( tab_size=2 )
console = CONSOLE
cs = CONSOLE

def install_path() -> Path:
	with pkg_path( APP_PKG_NAME, '__init__.py' ) as path:
		return path.parent.parent

def default_plugin_path() -> Path:
	with pkg_path( APP_PKG_NAME, f'{PLUGINS_PKG_NAME}/__init__.py' ) as path:
		return path

def default_resources_path() -> Path:
	with pkg_path( APP_PKG_NAME, f'{RESOURCES_DIRNAME}' ) as path:
		return path

# application context

@define
class ApplicationContext:

	# config/state files / fs
	config: Configuration = field( default=None )
	config_dir: str = field( default=None )
	config_file: str = field( default=None )
	state_file: str = field( default=None )
	config_fs: FS = field( default=None )

	# library fs
	lib_dir: str = field( default=None )
	lib_fs: FS = field( default=None )

	# database / fs
	db: Any = field( default=None )
	db_fs: FS = field( default=None )
	overlay_fs: FS = field( default=None )

	# takeouts
	takeouts_fs: FS = field( default=None )

	# auxillary FS
	log_fs: FS = field( default=None )
	var_fs: FS = field( default=None )
	backup_fs: FS = field( default=None )
	cache_fs: FS = field( default=None )
	tmp_fs: FS = field( default=None )
	imports_fs: FS = field( default=None )

	# needed?
	instance: Any = field( default=None )

	# app state
	state: Configuration = field( default=None )
	meta: Any = field( default=None ) # not used yet

	# plugins
	plugins: Dict[str, Any] = field( factory=dict )

	# registry
	registry: Any = field( default=None )

	# event hub
	hub: Any = field( default=None )

	# kwargs fields, not used, but needed for

	# todo: move this stuff away, as it does not belong here
	console: Console = field( default=CONSOLE )
	progress: Progress = field( default=None )
	task_id: Any = field( default=None )

	# internal fields

	__args__: Tuple[Any, ...] = field( default=(), alias='__args__' )
	__kwargs__: Dict[str, Any] = field( factory=dict, alias='__kwargs__' )

	# __root_fs__: OSFS = field( default=OSFS( root_path='/', expand_vars=True ), alias='__root_fs__' )
	__init_fs__: bool = field( default=True, alias='__init_fs__' )
	__apptime__: datetime = field( default=datetime.utcnow(), alias='__apptime__' )

	apptime: datetime = field( default=None )

	def __setup_config_fs__( self ):
		if self.config_fs:
			pass # reuse config fs, if already provided -> necessary for running test cases

		elif isinstance( cfg := self.__kwargs__.get( 'configuration' ), Configuration ):
			self.config = cfg

		elif isinstance( cfg, str ):
			path = abspath( expandvars( expanduser( cfg ) ) )
			if isdir( path ):
				self.config_fs = OSFS( root_path=path, expand_vars=True, create=True )
			elif isfile( path ):
				self.config_fs = OSFS( root_path=dirname( path ), expand_vars=True, create=True )
			else:
				head, tail = split( path )
				if tail.endswith( '.yaml' ):
					self.config_fs = OSFS( root_path=head, expand_vars=True, create=True )
				else:
					self.config_fs = OSFS( root_path=path, expand_vars=True, create=True )

		else:
			self.config_fs = OSFS( root_path=user_config_dir( APPNAME ), create=True )

		log.debug( f'config fs set to {self.config_fs}' )

		try:
			self.config_dir = self.config_fs.getsyspath( '/' )
			self.config_file = self.config_fs.getsyspath( f'/{CONFIG_FILENAME}' )
			self.state_file = self.config_fs.getsyspath( f'/{STATE_FILENAME}' )
		except NoSysPath:
			log.debug( f'config dir/file not set as FS does not support getsyspath()' )

	def __setup_config_state__( self ):
		settings_files = [ f'{install_path()}/{APP_PKG_NAME}/{DEFAULT_CONFIG_FILENAME}' ]
		appstate_files = [ f'{install_path()}/{APP_PKG_NAME}/{DEFAULT_STATE_FILENAME}' ]

		try:
			settings_files.append( self.config_fs.getsyspath( CONFIG_FILENAME ) )
		except NoSysPath:
			log.warning( f'no configuration file found in {self.config_fs}' )

		try:
			appstate_files.append( self.config_fs.getsyspath( STATE_FILENAME ) )
		except NoSysPath:
			log.warning( f'no appstate file found in {self.config_fs}' )

		self.config = Configuration( settings_files=settings_files, merge_enabled=True )
		self.state = Configuration( settings_files=appstate_files, merge_enabled=True )

	def __setup_cmd_args__( self ):
		self.__kwargs__.pop( 'configuration', None ) # remove configuration entry
		self.config.update( { k: v for k, v in self.__kwargs__.items() if v is not None } ) # update settings with values being not None

	def __setup_library__( self ):
		if self.lib_dir:
			library = self.lib_dir
		elif self.config.library:
			library = self.config.library
		else:
			library = self.config_dir

		# only try to create lib_fs if not already provided (this happens when running test cases)
		if not self.lib_fs:
			try:
				self.lib_fs = OSFS( root_path=library, expand_vars=True, create=True )
				self.lib_dir = self.lib_fs.getsyspath( '' )
				# self.db_fs = OSFS( root_path=f'{self.lib_fs.getsyspath( "" )}/{DB_DIRNAME}', create=True )
				# self.overlay_fs = OSFS( root_path=f'{self.lib_fs.getsyspath( "" )}/{OVERLAY_DIRNAME}', create=True )
			except (NoSysPath, TypeError):
				# lib fs creation by using library fails, create it as child of config fs
				self.lib_fs = _subfs( self.config_fs, '/' )
				# self.lib_fs = MemoryFS() if isinstance( self.config_fs, MemoryFS ) else _subfs( self.config_fs, '/' )

		# create db/overlay fs as child of lib_fs
		self.db_fs = _subfs( self.lib_fs, DB_DIRNAME )
		self.overlay_fs = _subfs( self.lib_fs, OVERLAY_DIRNAME )

	def __setup_aux__( self ):
		# takeouts
		self.takeouts_fs = _subfs( self.config_fs, TAKEOUT_DIRNAME )

		# logs, var etc.
		self.log_fs = _subfs( self.config_fs, LOG_DIRNAME )
		self.var_fs = _subfs( self.config_fs, VAR_DIRNAME )
		self.backup_fs = _subfs( self.config_fs, BACKUP_DIRNAME )
		self.cache_fs = _subfs( self.config_fs, CACHE_DIRNAME )
		self.tmp_fs = _subfs( self.var_fs, TMP_DIRNAME )
		self.imports_fs = _subfs( self.var_fs, IMPORT_DIRNAME )

#	def __init__( self, *args, **kwargs ):
#		extra_kwargs = { k: kwargs.pop( k, False ) for k in EXTRA_KWARGS }
		# noinspection PyUnresolvedReferences
#		self.__attrs_init__( *args, **kwargs, __kwargs__ = extra_kwargs  )

	def __attrs_post_init__( self ):
		# create config fs
		self.__setup_config_fs__()

		# read configuration/appstate
		self.__setup_config_state__()

		# update configuration with command line arguments
		self.__setup_cmd_args__()

		# set up library structure
		self.__setup_library__()

		# create default directories
		self.__setup_aux__()

	# main properties

	@property
	def cfg( self ) -> Configuration:
		"""
		Alias for self.config

		:return: configuration object
		"""
		return self.config

	@property
	def settings( self ) -> Configuration:
		"""
		Alias for self.config

		:return: configuration object
		"""
		return self.config

	@property
	def debug( self ) -> bool:
		return self.config.debug

	@property
	def verbose( self ) -> bool:
		return self.config.verbose

	@property
	def pretend( self ) -> bool:
		return self.config.pretend

	@property
	def force( self ) -> bool:
		return self.config.force

	@property
	def json( self ) -> bool:
		return self.config.json

	# lib/config related properties

	@property
	def lib_dir_path( self ) -> Path:
		return Path( self.lib_dir )

	@property
	def config_file_path( self ) -> Path:
		return Path( self.config_fs.getsyspath( CONFIG_FILENAME ) )

	@property
	def state_file_path( self ) -> Path:
		return Path( self.config_fs.getsyspath( STATE_FILENAME ) )

	# db related fs/dirs

	@property
	def db_dir( self ) -> str:
		return self.db_fs.getsyspath( '/' )

	@property
	def db_dir_path( self ) -> Path:
		return Path( self.db_dir )

	def db_fs_for( self, name: str ) -> FS:
		try:
			return OSFS( root_path=self.db_fs.getsyspath( name ), create=True )
		except (AttributeError, NoSysPath):
			return SubFS( self.db_fs, f'/{name}' )

	def plugin_fs( self, name: str ) -> FS:
		fs = MultiFS()
		fs.add_fs( name=OVERLAY_DIRNAME, fs=self.overlay_fs_for( name ), write=False )
		fs.add_fs( name=DB_DIRNAME, fs=self.db_fs_for( name ), write=True )
		return fs

	def plugin_dir( self, name: str ) -> str:
		return cast( MultiFS, self.plugin_fs( name ) ).get_fs( DB_DIRNAME ).getsyspath( '' )

	def plugin_dir_path( self, name ) -> Path:
		return Path( self.plugin_dir( name ) )

	@property
	def overlay_dir( self ) -> str:
		return self.overlay_fs.getsyspath( '' )

	def overlay_fs_for( self, name: str ) -> FS:
		try:
			return OSFS( root_path=self.overlay_fs.getsyspath( name ), create=True )
		except (AttributeError, NoSysPath):
			return SubFS( self.overlay_fs, f'/{name}' )

	@property
	def db_overlay_path( self ) -> Path:
		return Path( self.overlay_dir )

	# takeouts

	@property
	def takeouts_dir( self ) -> str:
		return self.takeouts_fs.getsyspath( '/' )

	@property
	def takeouts_dir_path( self ) -> Path:
		return Path( self.takeouts_dir )

	def takeout_fs( self, name: str ) -> FS:
		return OSFS( root_path=self.takeouts_fs.getsyspath( f'{name}' ), create=True )

	def takeout_dir( self, name: str ) -> str:
		return self.takeout_fs( name ).getsyspath( '' )

	def takeout_dir_path( self, name ) -> Path:
		return Path( self.takeout_dir( name ) )

	# var/log/etc.

	@property
	def log_dir( self ) -> str:
		return self.log_fs.getsyspath( '' )

	@property
	def log_file( self ) -> str:
		return self.log_fs.getsyspath( LOG_FILENAME )

	@property
	def log_file_path( self ) -> Path:
		return Path( self.log_file )

	@property
	def var_dir( self ) -> str:
		return self.var_fs.getsyspath( '' )

	@property
	def var_path( self ) -> Path:
		return Path( self.var_dir )

	@property
	def imports_dir( self ) -> str:
		return self.imports_fs.getsyspath( '' )

	@property
	def imports_path( self ) -> Path:
		return Path( self.imports_dir )

	def import_fs( self ) -> FS:
		return self.imports_fs.makedirs( f'{datetime.now( tz=tzlocal() ).strftime( "%y%m%d_%H%M%S" )}', recreate=True )

	@property
	def backup_dir( self ) -> str:
		return self.backup_fs.getsyspath( '' )

	@property
	def backup_path( self ) -> Path:
		return Path( self.backup_dir )

	# other helpers -> these need to be removed!

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
			columns = [
				TextColumn( '[progress.description]{task.description}' ),
				BarColumn(),
				TaskProgressColumn(),
				TimeElapsedColumn(),
				TextColumn( '/' ),
				TimeRemainingColumn(),
				TextColumn( '[cyan]to go[/cyan]' ),
				TextColumn( '{task.fields[msg]}' )
			]
			self.progress = Progress( *columns, console=self.console )
			self.progress.start()
			self.task_id = self.progress.add_task( description=description, total=total, msg='' )

	def total( self, total=None ):
		if self.progress is None:
			self.start( total=total )
		else:
			self.progress.update( task_id=self.task_id, total=total )

	def advance( self, msg: str = None, advance: float = 1 ):
		if self.verbose:
			self.pp( msg )
		else:
			if not self.progress: # todo: improve, this might happen during testing strava ...
				return

			self.progress.update( task_id=self.task_id, advance=advance, msg=msg )

	def complete( self, msg: str = None ):
		if self.verbose:
			if msg:
				self.pp( msg )
		else:
			if not self.progress: # todo: improve, this might happen during testing strava ...
				return

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

	# plugin configuration helpers

	def plugin_config_state( self, name, as_dict: bool = False ) -> Tuple[DynaBox, DynaBox]:
		name = name.lower()
		try:
			cfg = self.config.plugins[name] or DynaBox()
		except BoxKeyError:
			log.error( f'unable to find configuration area for plugin {name}' )
			cfg = DynaBox()

		try:
			state = self.state.plugins[name] or DynaBox()
		except BoxKeyError:
			log.error( f'unable to find app state area for plugin {name}' )
			state = DynaBox()

		return cfg, state

	def dump_config_state( self ) -> None:
		self.dump_config()
		self.dump_state()

	def dump_config( self ) -> None:
		self._dump_settings( self.config, CONFIG_FILENAME )

	def dump_state( self ) -> None:
		self._dump_settings( self.state, STATE_FILENAME )

	def _dump_settings( self, settings: Configuration, filename: str ):
		s = safe_dump( self._lower_dict( settings.as_dict() ), sort_keys=True, allow_unicode=True )
		self.config_fs.writetext( filename, s )

	def _lower_dict( self, d: Dict ) -> Dict:
		for k, v in d.copy().items():
			if isinstance( v, dict ):
				d.pop( k )
				d[f'{k.lower()}'] = v
				self._lower_dict( v )
			else:
				d.pop( k )
				d[f'{k.lower()}'] = v
		return d

# convenience helper

def _subfs( parent: FS, path: str ) -> SubFS:
	parent.makedirs( path, recreate=True )
	return SubFS( parent_fs=parent, path=path )

# global application context

CURRENT_CONTEXT: Optional[ApplicationContext] = None

def current_ctx() -> ApplicationContext:
	"""
	Returns the currently active context.

	:return: active application context
	"""
	global CURRENT_CONTEXT
	return CURRENT_CONTEXT

def set_current_ctx( ctx: ApplicationContext ) -> ApplicationContext:
	"""
	Sets the current application context.

	:param ctx: context to set
	:return: current context, for convenience
	"""
	global CURRENT_CONTEXT
	CURRENT_CONTEXT = ctx if ctx else CURRENT_CONTEXT
	return CURRENT_CONTEXT
