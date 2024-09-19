from __future__ import annotations

from atexit import register as register_atexit
from logging import getLogger
from typing import ClassVar, Optional, Tuple

from attrs import define, field
from dynaconf import Dynaconf as Configuration
from textual.message import Message
from textual.message_pump import MessagePump

from tracs import setup_console_logging, setup_file_logging
from tracs.activity import configure_formatters as configure_activity_formatters
from tracs.config import ApplicationContext, set_current_ctx
from tracs.db import ActivityDb
from tracs.pluginmgr import PluginManager
from tracs.registry import Registry
from tracs.rules import RuleParser
from tracs.utils import UCFG

log = getLogger( __name__ )

class PrintMessage( Message ):

	def __init__( self, text: str ) -> None:
		super().__init__()
		self.text = text

class MessageHub( MessagePump ):

	def __init__( self ) -> None:
		super().__init__()
		self.app._register( None, self )

	def print( self, text: str ) -> bool:
		return self.post_message( PrintMessage( text ) )

	def on_print_message( self, message: PrintMessage ) -> None:
		print( message.text )

@define( init=False )
class Application:

	_instance: ClassVar[Application] = None  # application singleton

	_ctx: ApplicationContext = field( default=None, alias='_ctx' )
	_db: ActivityDb = field( default=None, alias='_db' )
	_hub: MessageHub = field( default=None, alias='_hub' )
	_registry: Registry = field( default=None, alias='_registry' )
	_parser: RuleParser = field( default=None, alias='_parser' )

	_config: Configuration = field( default=None, alias='_config' )
	_state: Configuration = field( default=None, alias='_state' )

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
		instance.__setup__( *args, **kwargs )
		return instance

	# 'None' as default value means value has not been provided from the outside (via command line switch)
	def __setup__( self, *args, **kwargs ):
		# console logging setup --
		setup_console_logging( kwargs.get( 'verbose', False ), kwargs.get( 'debug', False ), kwargs.get( 'json', False ) )

		# log command line flags
		log.debug( f'triggered CLI with flags {kwargs}' )

		# config_dir, config_file = _config_dir_file( kwargs.get( 'configuration' ) )

		# try:
		# 	configuration = expanduser( expandvars( kwargs.pop( 'configuration', None ) ) )
		# 	if configuration and Path( configuration ).is_dir():
		# 		kwargs['config_dir'] = configuration
		# 	elif configuration and Path( configuration ).is_file():
		# 		kwargs['config_file'] = configuration
		# 	else:
		# 		pass
		# except TypeError:
		# 	pass
		#
		# try:
		# 	library = expanduser( expandvars( kwargs.pop( 'library', None ) ) )
		# 	if library and Path( library ).is_dir():
		# 		kwargs['lib_dir'] = library
		# 	else:
		# 		pass
		# except TypeError:
		# 	pass

		# create context, based on cfg_dir
		self._ctx = ApplicationContext( __args__=args, __kwargs__=kwargs )
		self._config = self._ctx.config
		self._state = self._ctx.state
		set_current_ctx( self._ctx )

		# file logging setup after configuration has been loaded --
		setup_file_logging( self._ctx.verbose, self._ctx.debug, self._ctx.log_file_path )

		# print context configuration
		log.debug( f'using configuration from {self._ctx.config_dir} and library in {self._ctx.lib_dir}' )

		# init plugin manager/load plugins
		PluginManager.init( (self._config.pluginpath or '').split( ' ' ) )

		# create registry
		self._registry = Registry.create(
			keywords=PluginManager.keywords,
			normalizers=PluginManager.normalizers,
			resource_types=PluginManager.resource_types,
			importers=PluginManager.importers,
			virtual_fields=PluginManager.virtual_fields,
			setups=PluginManager.setups,
			services=PluginManager.services,
			ctx=self._ctx,
		)

		# open db from config_dir
		self._db = ActivityDb(
			path=self._ctx.db_dir_path,
			read_only=self._ctx.pretend,
			enable_index=self.ctx.config.db.index,
			summary_types=[ t.type for t in self._registry.summary_types() ],
			recording_types=[ t.type for t in self._registry.recording_types() ],
		)
		self._ctx.db = self._db # todo: really put db into ctx? or keep it here?

		# create parser
		self._parser = RuleParser(
			keywords=self.registry.keywords,
			normalizers=self.registry.normalizers,
		)

		# create message hub
		self._hub = MessageHub()
		self._ctx.hub = self._hub

		# ---- announce context/configuration to utils module + configure formatters ----
		UCFG.reconfigure( self._ctx.config )
		configure_activity_formatters( self._ctx.config.formats )

		# ---- register cleanup functions ----
		register_atexit( self._ctx.db.close )
		register_atexit( self._ctx.dump_state )

	# properties

	@property
	def ctx( self ) -> ApplicationContext:
		return self._ctx

	@property
	def db( self ) -> ActivityDb:
		return self._db

	@property
	def registry( self ) -> Registry:
		return self._registry

	@property
	def parser( self ) -> RuleParser:
		return self._parser

	@property
	def config( self ) -> Configuration:
		return self._config

	@property
	def state( self ) -> Configuration:
		return self._state

	@property
	def as_tuple( self ) -> Tuple[ApplicationContext, ActivityDb]:
		return self.ctx, self.db

def _config_dir_file( configuration: Optional[str] ) -> Tuple[Optional[str], Optional[str]]:
	return None, None