
from __future__ import annotations

from atexit import register as register_atexit
from logging import DEBUG
from logging import INFO
from logging import FileHandler
from logging import Formatter
from logging import getLogger
from logging import StreamHandler
from sys import stderr

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
	def __setup__( self, *args, **kwargs ):
		# ---- create context, based on cfg_dir ----
		self._ctx = ApplicationContext( **kwargs )
		log.debug( f'using {self._ctx.config_dir} as configuration directory' )
		log.debug( f'using {self._ctx.lib_dir} as library' )

		# ---- logging setup: only possible after configuration has been loaded --
		self._setup_logging( self._ctx )

		# ---- file logging setup: only possible after library configuration --------
		self._setup_file_logging( self._ctx )

		# ---- open db from config_dir ----------------------------------------------
		self._ctx.db = ActivityDb( path=self._ctx.db_dir_path, read_only=self._ctx.pretend )

		# load plugins
		from .registry import load as load_plugins
		load_plugins()

		# ---- create service instances ----
		Registry.instantiate_services( ctx=self._ctx )

		# ---- announce context/configuration to utils module ----
		UCFG.reconfigure( self._ctx.config )

		# ---- register cleanup functions ----
		register_atexit( self._ctx.db.close )
		register_atexit( self._ctx.dump_state )

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
		file_level = DEBUG if ctx.debug else INFO
		file_format = '[%(asctime)s] %(levelname)s: %(message)s'
		date_format = '%Y-%m-%d %H:%M:%S'
		file_handler = FileHandler( ctx.log_file_path, 'a' )
		file_handler.setLevel( file_level )
		file_handler.setFormatter( Formatter( file_format, date_format ) )

		getLogger( APPNAME ).addHandler( file_handler )

	# ---- context ---------------------------------------------------------------

	@property
	def ctx( self ) -> ApplicationContext:
		return self._ctx
