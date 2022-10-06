
from __future__ import annotations

from atexit import register as register_atexit
from logging import DEBUG
from logging import INFO
from logging import FileHandler
from logging import Formatter
from logging import getLogger
from logging import StreamHandler
from pathlib import Path
from sys import exit
from sys import stderr
from typing import Mapping

from confuse import Configuration

from .config import ApplicationConfig as cfg
from .config import ApplicationContext
from .config import ApplicationState as state
from .config import APPNAME
from .config import BACKUP_DIRNAME
from .config import CONFIG_FILENAME
from .config import DB_DIRNAME
from .config import DB_FILENAME
from .config import GlobalConfig as gc
from .config import LOG_DIRNAME
from .config import LOG_FILENAME
from .config import OVERLAY_DIRNAME
from .config import STATE_FILENAME
from .config import TAKEOUT_DIRNAME
from .db import ActivityDb
from .plugins import Registry
from .service import Service

log = getLogger( __name__ )

class Application( object ):

	_instance = None # application singleton

	@classmethod
	def instance( cls, *args, **kwargs ):
		if cls._instance is None:
			cls._instance = Application.__new__( cls, *args, **kwargs )
		return cls._instance

	# constructor
	def __init__( self ):
		raise RuntimeError( 'instance can only be created by using Application.instance( cls ) method' )

	@classmethod
	def __new__( cls, *args, **kwargs ):
		instance = super( Application, cls ).__new__( cls )
		instance.__setup__( **kwargs )
		return instance

	# 'None' as default value means value has not been provided from the outside (via command line switch)
	def __setup__( self, ctx: ApplicationContext = None, config_dir: Path = None, lib_dir: Path = None, verbose: bool = None, debug: bool = None, force: bool = None, pretend: bool = None ):
		# save application context
		self._ctx = ctx

		# ---- configuration directory initialization/handling -----
		# if config dir is provided, it needs to exist
		if config_dir:
			if not config_dir.is_absolute():
				config_dir = Path( Path.cwd(), config_dir )
			if not config_dir.exists():
				log.fatal( f'configuration path \'{config_dir}\' does not exist, exiting ...' )  # todo: ask to create path?
				exit( -1 )
			elif not config_dir.is_dir():
				log.fatal( f'configuration path \'{config_dir}\' is not a directory, exiting ...' )  # todo: ask to create path?
				exit( -1 )

		self._cfg = cfg
		self._state = state

		# config_dir has been set?
		if config_dir:
			self._config_dir = config_dir
		else:
			self._config_dir = Path( self._cfg.config_dir() )

		# load configuration + state from user location if it exists
		if self.cfg_file.exists():
			self._cfg.set_file( self.cfg_file )
			ctx.config.set_file( self.cfg_file )

		if self.state_file.exists():
			self._state.set_file( self.state_file )
			ctx.state.set_file( self.state_file )

		# ---- evaluate provided parameters (configuration/command line) ------------
		ctx.force = force if force is not None else ctx.config['force'].get()
		ctx.pretend = pretend if pretend is not None else ctx.config['pretend'].get()
		ctx.verbose = verbose if verbose is not None else ctx.config['verbose'].get()

		# todo: remove when application context support is fully implemented
		if force is not None:
			self._cfg['force'] = force
		if debug is not None:
			self._cfg['debug'] = debug
		if verbose is not None:
			self._cfg['verbose'] = verbose
		if pretend is not None:
			self._cfg['pretend'] = pretend

		# ---- logging setup: only possible after configuration has been loaded --
		self._setup_logging()

		# ---- library initialization/handling -----
		# if library dir is provided, it needs to exist
		if lib_dir and not lib_dir.exists():
			if not lib_dir.is_absolute():
				lib_dir = Path( Path.cwd(), lib_dir )
			if not lib_dir.exists():
				log.fatal( f'library path \'{lib_dir}\' does not exist, exiting ...' )  # todo: ask to create path?
				exit( -1 )
			elif not lib_dir.is_dir():
				log.fatal( f'library path \'{lib_dir}\' is not a directory, exiting ...' )  # todo: ask to create path?
				exit( -1 )

		# default case: use config dir as lib_dir
		self._lib_dir = self.cfg_dir
		# check if library has been set via config file -> wins over default case
		if self._cfg['library']:
			self._lib_dir = self._cfg['library'].as_path()
		# lib_dir has been set via parameter ? -> parameter wins over definition from config file
		if lib_dir:
			self._lib_dir = lib_dir

		# ---- file logging setup: only possible after library configuration --------
		self._setup_file_logging()

		# ---- open db from config_dir ----------------------------------------------
		cache = self._cfg['db']['cache'].get()
		self._db_dir = Path( self._lib_dir, DB_DIRNAME )
		self._db = ActivityDb( path=self._db_dir, cache=cache )
		self._db_file = self._db.db_path
		self._meta_file = self._db.metadata_path
		gc.db = self._db

		# ---- configure overlay from db_dir ----------------------------------------
		self._overlay_dir = Path( self.db_dir, OVERLAY_DIRNAME )
		self._takeout_dir = Path( self.db_dir, TAKEOUT_DIRNAME )

		# announce library paths to services
		for name, service in Registry.services.items():
			service.base_path = Path( self._db_dir, name )

		# announce paths to application context
		ctx.cfg_dir = self.cfg_dir
		ctx.db_dir = self.db_dir
		ctx.lib_dir = self.lib_dir
		ctx.overlay_dir = self.overlay_dir
		ctx.takeout_dir = self.takeout_dir

		# ---- announce fields to global config
		gc.cfg_dir = self.cfg_dir
		gc.db_dir = self.db_dir
		gc.db_file = self.db_file
		gc.lib_dir = self.lib_dir

		# log some internal information
		log.debug( f'using configuration directory at {self._config_dir}' )
		log.debug( f'using library directory at {self._lib_dir}' )
		log.debug( f'using database file at {self.db_file}' )
		log.debug( f'using database metadata at {self._meta_file}' )

		# ---- register cleanup functions ----
		register_atexit( self._db.activities_db.close )
		register_atexit( self._db.resources_db.close )
		register_atexit( self.dump_state )

	def _setup_logging( self ):
		debug = self._cfg['debug'].get()
		verbose = self._cfg['verbose'].get()
		console_level = INFO if not debug else DEBUG
		console_format = '%(message)s'
		date_format = '%Y-%m-%d %H:%M:%S'
		if verbose and debug:
			console_format = '[%(asctime)s] %(levelname)s: %(message)s'
		elif verbose and not debug:
			console_format = '[%(levelname)s] %(message)s'

		logger = getLogger( APPNAME )
		logger.setLevel( console_level )
		if len( logger.handlers ) == 0: # add stream handler -> necessary during test case running
			logger.addHandler( StreamHandler( stderr ) )
		logger.handlers[0].setLevel( console_level )
		logger.handlers[0].setFormatter( Formatter( console_format, date_format ) )

	def _setup_file_logging( self ):
		self.log_dir.mkdir( parents=True, exist_ok=True )

		file_level = DEBUG if self._cfg['debug'].get() else INFO
		file_format = '[%(asctime)s] %(levelname)s: %(message)s'
		date_format = '%Y-%m-%d %H:%M:%S'
		file_handler = FileHandler( self.log_file, 'a' )
		file_handler.setLevel( file_level )
		file_handler.setFormatter( Formatter( file_format, date_format ) )

		getLogger( APPNAME ).addHandler( file_handler )

	# get/set item is forwarded to _cfg
	def __getitem__( self, key ):
		return self._cfg[key]

	def __setitem__( self, key, value ):
		self._cfg[key] = value

	# ---- context ---------------------------------------------------------------

	@property
	def ctx( self ) -> ApplicationContext:
		return self._ctx

	# ---- path-related properties ----

	@property
	def lib_dir( self ) -> Path:
		return self._lib_dir

	@property
	def overlay_dir( self ) -> Path:
		return self._overlay_dir

	@property
	def takeout_dir( self ) -> Path:
		return self._takeout_dir

	@property
	def cfg_dir( self ) -> Path:
		return self._config_dir

	@property
	def cfg_file( self ) -> Path:
		return Path( self.cfg_dir, CONFIG_FILENAME )

	@property
	def state_file( self ) -> Path:
		return Path( self.cfg_dir, STATE_FILENAME )

	@property
	def db_dir( self ) -> Path:
		return Path( self.lib_dir, DB_DIRNAME )

	@property
	def db_file( self ) -> Path:
		return Path( self.db_dir, DB_FILENAME )

	@property
	def log_dir( self ) -> Path:
		return Path( self.cfg_dir, LOG_DIRNAME )

	@property
	def log_file( self ) -> Path:
		return Path( self.log_dir, LOG_FILENAME )

	@property
	def backup_dir( self ) -> Path:
		return Path( self.db_dir, BACKUP_DIRNAME )

	# ---- Activity related properties/paths -----

	def service_path( self, srv_name: str ) -> Path:
		return Path( self.db_dir, srv_name )

	# ---- configuration/state objects + dump ----

	@property
	def cfg( self ) -> Configuration:
		return self._cfg

	@property
	def state( self ) -> Configuration:
		return self._state

	def dump_cfg( self ) -> None:
		if not cfg['pretend'].get():
			with open( self.cfg_file, 'w+' ) as cf:
				#cf.write( dump_yaml( load_yaml( self._cfg.dump( full=True ), Loader=FullLoader ), sort_keys=True ) )
				cf.write( self._cfg.dump( full=True ) )
		else:
			log.info( f'pretending to write config file to {self.cfg_file}' )

	def dump_state( self ) -> None:
		if not cfg['pretend'].get():
			with open( self.state_file, 'w+' ) as sf:
				#sf.write( dump_yaml( load_yaml( self._state.dump( full=True ), Loader=FullLoader ), sort_keys=True ) )
				sf.write( self._state.dump( full=True ) )
		else:
			log.info( f'pretending to write state file to {self.state_file}' )

	# ---- internal db ----

	@property
	def db( self ) -> ActivityDb:
		return self._db

	# ---- registered services ----
	@property
	def services( self ) -> Mapping[str, Service]:
		return Registry.services
