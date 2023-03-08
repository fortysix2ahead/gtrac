
from __future__ import annotations

from atexit import register as register_atexit
from logging import DEBUG
from logging import INFO
from logging import FileHandler
from logging import Formatter
from logging import getLogger
from logging import StreamHandler
from pathlib import Path
from sys import stderr

from confuse.exceptions import ConfigTypeError

from .config import ApplicationContext
from .config import APPNAME
from .db import ActivityDb
from .registry import Registry
from .utils import UCFG

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
	def __setup__( self, ctx: ApplicationContext = None, config_dir: str = None, lib_dir: str = None, verbose: bool = None, debug: bool = None, force: bool = None, pretend: bool = None ):

		# ---- configuration directory initialization -----
		config_dir = Path( Path.cwd(), config_dir ).resolve() if config_dir else Path( Path.home(), '.config', APPNAME )
		config_dir.mkdir( parents=True, exist_ok=True )

		log.debug( f'using {config_dir} as configuration directory' )

		# ---- (default) library location ----
		lib_dir_str = lib_dir # save parameter for later
		lib_dir = Path( Path.cwd(), lib_dir ).resolve() if lib_dir else Path( config_dir )

		log.debug( f'using {lib_dir} as default library directory' )

		# ---- create context, based on cfg_dir ----
		ctx = ApplicationContext( cfg_dir=config_dir, lib_dir=lib_dir )
		self._ctx = ctx

		# load configuration + state from user location if it exists -> this can also be moved into the context later
		if ctx.cfg_file.exists():
			ctx.config.set_file( ctx.cfg_file )

		if ctx.state_file.exists():
			ctx.state.set_file( ctx.state_file )

		# ---- evaluate provided parameters (configuration/command line) ------------
		ctx.debug = debug if debug is not None else ctx.config['debug'].get()
		ctx.force = force if force is not None else ctx.config['force'].get()
		ctx.pretend = pretend if pretend is not None else ctx.config['pretend'].get()
		ctx.verbose = verbose if verbose is not None else ctx.config['verbose'].get()

		# ---- logging setup: only possible after configuration has been loaded --
		self._setup_logging( ctx )

		# ---- library initialization/handling -----

		# lib_dir has been set via parameter ? -> if yes, parameter wins over definition in config file
		if not lib_dir_str:
			# try to read from config file ... if that fails we'll use the previously defined default
			try:
				lib_dir = ctx.config['library'].as_path()
				# todo: update context ...
			except ConfigTypeError:
				pass

		lib_dir.mkdir( parents=True, exist_ok=True )

		log.debug( f'using {lib_dir} as library directory' )

		# ---- file logging setup: only possible after library configuration --------
		self._setup_file_logging( ctx )

		# ---- open db from config_dir ----------------------------------------------
		ctx.db = ActivityDb( path=ctx.db_dir, read_only=ctx.pretend )

		# load plugins
		from .registry import load as load_plugins
		load_plugins()

		# ---- create service instances ----
		Registry.instantiate_services( ctx=ctx, base_path=ctx.db_dir, overlay_path=ctx.overlay_dir )

		# ---- announce context/configuration to utils module ----
		UCFG.reconfigure( ctx.config )

		# ---- register cleanup functions ----
		register_atexit( ctx.db.close )
		register_atexit( ctx.dump_state )

	# noinspection PyMethodMayBeStatic
	def _setup_logging( self, ctx: ApplicationContext ):
		debug = ctx.debug
		verbose = ctx.verbose
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

	# noinspection PyMethodMayBeStatic
	def _setup_file_logging( self, ctx: ApplicationContext ):
		ctx.log_dir.mkdir( parents=True, exist_ok=True )

		file_level = DEBUG if ctx.debug else INFO
		file_format = '[%(asctime)s] %(levelname)s: %(message)s'
		date_format = '%Y-%m-%d %H:%M:%S'
		file_handler = FileHandler( ctx.log_file, 'a' )
		file_handler.setLevel( file_level )
		file_handler.setFormatter( Formatter( file_format, date_format ) )

		getLogger( APPNAME ).addHandler( file_handler )

	# ---- context ---------------------------------------------------------------

	@property
	def ctx( self ) -> ApplicationContext:
		return self._ctx
