
from __future__ import annotations

from enum import Enum
from importlib import import_module
from inspect import getmembers
from inspect import isclass
from logging import getLogger
from pathlib import Path
from pkgutil import walk_packages
from re import match
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from confuse import NotFoundError
from dataclass_factory import Factory
from dataclass_factory import Schema

from tracs.config import ApplicationContext
from tracs.config import KEY_CLASSIFER
from tracs.handlers import Handler
from tracs.handlers import Importer
from tracs.protocols import Service
from tracs.resources import ResourceType

log = getLogger( __name__ )

NS_PLUGINS = 'tracs.plugins'

class EventTypes( Enum ):

	activity_field_resolver_registered = 'activity_field_resolver_registered'
	plugin_loaded = 'plugin_loaded'
	resource_loaded = 'resource_loaded'
	service_created = 'service_created'

class Registry:

	activity_field_resolvers = {}
	classifier: str = KEY_CLASSIFER
	ctx: ApplicationContext = None
	document_classes: Dict[str, Type] = {}
	document_types: Dict[str, Type] = {}
	downloaders = {}
	event_listeners = {}
	dataclass_factory = Factory( debug_path=True, schemas={} )
	fetchers = {}
	handlers: Dict[str, List[Handler]] = {}
	importers: Dict[str, List[Importer]] = {}
	resource_types: Dict[str, Type] = {}
	services: Dict[str, Service] = {}
	service_classes: Dict[str, Type] = {}

	@classmethod
	def instantiate_services( cls, ctx: Optional[ApplicationContext] = None, **kwargs ):
		_ctx = ctx if ctx else Registry.ctx
		base_path = kwargs.get( 'base_path' )
		overlay_path = kwargs.get( 'overlay_path' )
		for name, service_type in Registry.service_classes.items():
			service_base_path = Path( base_path, name )
			service_overlay_path = Path( overlay_path, name )

			# find config/state values
			try:
				service_cfg = ctx.config['plugins'][name].get() or {}
			except NotFoundError:
				service_cfg = {}
			try:
				service_state = ctx.state['plugins'][name].get() or {}
			except NotFoundError:
				service_state = {}

			Registry.services[name] = service_type( ctx=ctx, **{ **kwargs, **service_cfg, **service_state, **{ 'base_path': service_base_path, 'overlay_path': service_overlay_path } } )
			# log.debug( f'created service instance {name}, with base path {service_base_path}' )
			Registry.notify( EventTypes.service_created, Registry.services[name] )

	@classmethod
	def service_names( cls ) -> List[str]:
		return list( Registry.services.keys() )

	@classmethod
	def service_for( cls, uid: str = None ) -> Service:
		return Registry.services.get( uid.split( ':', maxsplit= 1 )[0] )

	# resource types

	@classmethod
	def register_resource_type( cls, resource_type ) -> None:
		Registry.resource_types[resource_type.type] = resource_type

	# noinspection PyUnresolvedReferences
	@classmethod
	def resource_type_for_extension( cls, extension: str ) -> Optional[ResourceType]:
		return next( (rt for rt in Registry.resource_types.values() if rt.extension() == extension), None )

	@classmethod
	def resource_type_for_suffix( cls, suffix: str ) -> Optional[str]:
		# first round: prefer suffix in special part of type: 'gpx' matches 'application/xml+gpx'
		for key in Registry.importers.keys():
			if m := match( f'^(\w+)/(\w+)\+{suffix}$', key ):
				return key

		# second round: suffix after slash: 'gpx' matches 'application/gpx'
		for key in Registry.importers.keys():
			if m := match( f'^(\w+)/{suffix}(\+([\w-]+))?$', key ):
				return key

		return None

	# field resolvers
	@classmethod
	def register_activity_field_resolver( cls, field: str, fn: Callable ) -> None:
		Registry.activity_field_resolvers[field] = fn
		Registry.notify( EventTypes.activity_field_resolver_registered, field=field, resolver=fn )

	# event handling

	@classmethod
	def notify( cls, event_type: EventTypes, *args, **kwargs ) -> None:
		for fn in Registry.event_listeners.get( event_type, [] ):
			fn( *args, **kwargs )

	@classmethod
	def register_listener( cls, event_type: EventTypes, fn: Callable ) -> None:
		if not event_type in Registry.event_listeners.keys():
			Registry.event_listeners[event_type] = []
		Registry.event_listeners.get( event_type ).append( fn )

	# handlers

	@classmethod
	def handler_for( cls, type: str ) -> Optional[Handler]:
		handler_list = Registry.handlers.get( type ) or []
		return handler_list[0] if len( handler_list ) > 0 else None

	@classmethod
	def handlers_for( cls, type: str ) -> List[Handler]:
		return Registry.handlers.get( type ) or []

	@classmethod
	def register_handler( cls, handler: Handler, type: str ) -> None:
		handler_list = Registry.handlers.get( type ) or []
		if handler not in handler_list:
			handler_list.append( handler )
			Registry.handlers[type] = handler_list
			log.debug( f'registered handler {handler.__class__} for type {type}' )

	# importers

	@classmethod
	def importer_for( cls, type: str ) -> Optional[Importer]:
		importer_list = Registry.importers.get( type ) or []
		return importer_list[0] if len( importer_list ) > 0 else None

	@classmethod
	def importers_for( cls, type: str ) -> List[Importer]:
		return Registry.importers.get( type ) or []

	@classmethod
	def importers_for_suffix( cls, suffix: str ) -> List[Importer]:
		importers = []
		for key, value in Registry.importers.items():
			if m := match( f'^(\w+)/{suffix}(\+([\w-]+))?$', key ) or match( f'^(\w+)/(\w+)\+{suffix}$', key ):
				# g1, g2, g3 = m.groups()
				if '+' in key:
					importers = value + importers
				else:
					importers.extend( value )
		return importers

	@classmethod
	def register_importer( cls, importer: Importer, type: str ):
		importer_list = Registry.importers.get( type ) or []
		if importer not in importer_list:
			importer_list.append( importer )
			Registry.importers[type] = importer_list
			log.debug( f'registered importer {importer.__class__} for type {type}' )

	@classmethod
	def register_functions( cls, functions: Dict[Union[str, Tuple[str, str]], Callable], dictionary: Dict ) -> None:
		for item_key, item_value in functions.items():
			dictionary[item_key] = item_value

	@classmethod
	def register_function( cls, key: str or Tuple[str, str], fn: Callable, dictionary: Mapping ) -> Callable:
		if not key or not fn:
			log.warning( 'unable to register function with an empty key and/or function' )
		else:
			if type( key ) is tuple and key[0] is None: # allow (None, 'field') as key and treat it as 'field'
				key = key[1]
			dictionary[key] = fn

		return fn

	@classmethod
	def unregister_function( cls, key: str or Tuple[str, str], dictionary: Dict ) -> None:
		del dictionary[key]

	@classmethod
	def function_for( cls, key: str or Tuple[str, str], dictionary: Mapping ) -> Optional[Callable]:
		return dictionary.get( key )

	@classmethod
	def functions_for( cls, key: Optional[str], dictionary: Mapping ) -> Dict[str, Callable]:
		rval = {}
		for item_key, item_fn in dictionary.items():
			if key and type( item_key ) is tuple and key == item_key[0]:
				rval[item_key[1]] = item_fn
			elif not key and type( item_key ) is str:
				rval[item_key] = item_fn
		return rval

def _spec( func: Callable ) -> Tuple[str, str]:
	"""
	Helper for examining a provided function. Returns the module name and the name of the function as a tuple.
	The module only contains the name of the module alone, not the fully qualified name.

	:param func: function to be examined
	:return: module + name as a tuple
	"""
	name = None
	module = None
	#members = getmembers( func )
	for k, v in getmembers( func ):
		if k == '__name__':
			name = v
		elif k == '__module__':
			module = v.rsplit( '.', 1 )[1]

	#print( getfullargspec( fn ) )

	return module, name

def _register( args, kwargs, dictionary, callable_fn = False ) -> Union[Type, Callable]:
	"""
	Helper for registering mappings returned from the provided decorated function to the provided dictionary.

	:param args:
	:param kwargs:
	:param dictionary:
	:param callable_fn:
	:return: returns the provided callable (as convenience for callers)
	"""
	def decorated_fn( fn ):
		dec_ns, dec_name = _spec( fn )
		if callable_fn:
			dec_call_result = fn()
			for dec_fn_name, dec_fn_value in dec_call_result.items():
				if kwargs['classifier']:
					Registry.register_function( (kwargs['classifier'], dec_fn_name), dec_fn_value, dictionary )
				else:
					Registry.register_function( dec_fn_name, dec_fn_value, dictionary )
		else:
			if kwargs['classifier']:
				Registry.register_function( (kwargs['classifier'], dec_name), fn, dictionary )
			else:
				Registry.register_function( dec_name, fn, dictionary )

		return fn

	# call via standard decorator, no namespace argument is provided, namespace is taken from module containing the function
	if len( args ) == 1:
		ns, name = _spec( args[0] )
		if callable_fn:
			call_result = args[0]()
			for fn_name, fn_value in call_result.items():
				Registry.register_function( (ns, fn_name), fn_value, dictionary )
		else:
			Registry.register_function( (ns, name), args[0], dictionary )
		return args[0]
	# call via decorator with arguments, namespace argument is provided
	elif len( args ) == 0 and 'classifier' in kwargs:
		return decorated_fn
	else:
		raise RuntimeError( 'unable to register function -> this needs to be reported' )

def resourcetype( *args, **kwargs ):
	def reg_resource_type( cls ):
		Registry.register_resource_type( ResourceType( activity_cls = cls, **kwargs ) )
		Registry.dataclass_factory.schemas[cls] = Schema( omit_default=True, skip_internal=True, unknown='unknown' )
		return cls
	return reg_resource_type if len( args ) == 0 else args[0]

def service( cls: Type ):
	if isclass( cls ):
		module, name = _spec( cls )
		Registry.service_classes[module] = cls
		log.debug( f'registered service class {cls}' )
		return cls
	else:
		raise RuntimeError( 'only classes can be used with the @service decorator' )

def document( *args, **kwargs ):
	def document_class( cls ):
		if isclass( cls ):
			if document_type := kwargs.get( 'type' ):
				Registry.document_types[document_type] = cls
				log.debug( f"registered document class {cls} with type {document_type}" )

			if document_namespace := kwargs.get( 'namespace' ):
				Registry.document_classes[document_namespace] = cls
				log.debug( f"registered document class {cls} with namespace {document_namespace}" )

			return cls
		else:
			raise RuntimeError( 'only classes can be used with the @document decorator' )

	if len( args ) == 0:
		return document_class
	elif len( args ) == 1 and isclass( args[0] ):
		module_arg, name_arg = _spec( args[0] )
		Registry.document_classes[module_arg] = args[0]
		log.debug( f'registered document class {args[0]} with namespace {module_arg}' )
		return args[0]
	else:
		raise RuntimeError( 'only classes can be used with the @document decorator' )

def importer( *args, **kwargs ):
	def importer_class( cls ):
		if isclass( cls ):
			instance: Importer = cast( Importer, cls() )
			Registry.register_importer( instance, kwargs['type'] )
			return cls
		else:
			raise RuntimeError( 'only classes can be decorated with the @handler decorator' )

	if len( args ) == 0 and 'type' in kwargs:
		return importer_class
	elif len( args ) == 1:
		importer_class( args[0] )

def fetch( fn ):
	return Registry.register_function( _spec( fn ), fn, Registry.fetchers )

def download( fn ):
	return Registry.register_function( _spec( fn ), fn, Registry.downloaders )

def load( plugin_pkgs: List[str] = None, disabled: List[str] = None ):
	plugin_pkgs = plugin_pkgs if plugin_pkgs else [NS_PLUGINS]
	disabled = disabled if disabled else [ 'empty' ]

	for plugin_pkg in plugin_pkgs:
		plugins_module = import_module( plugin_pkg )
		for finder, name, ispkg in walk_packages( plugins_module.__path__ ):
			if name not in disabled:
				qname = f'{plugin_pkg}.{name}'
				try:
					plugin = import_module( qname )
					Registry.notify( EventTypes.plugin_loaded, plugin )
					log.debug( f'imported plugin {plugin}' )
				except ModuleNotFoundError:
					log.debug( f'error imporing module {qname}' )
			else:
				log.debug( f'skipping import of disabled plugin {name} in package {plugin_pkg}' )
