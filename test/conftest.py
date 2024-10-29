from datetime import datetime
from importlib.resources import path as pkgpath
from logging import getLogger
from os.path import dirname
from pathlib import Path
from shutil import copytree, rmtree
from typing import Dict, List, NamedTuple, Optional

from fs.base import FS
from fs.copy import copy_fs
from fs.memoryfs import MemoryFS
from fs.osfs import OSFS
from fs.subfs import SubFS
from pytest import fixture

from tracs.config import ApplicationContext, DB_DIRNAME, set_current_ctx
from tracs.db import ActivityDb
from tracs.pluginmgr import PluginManager
from tracs.registry import Registry
from tracs.rules import RuleParser
from tracs.service import Service
from tracs.utils import FsPath
from .helpers import get_db_as_json, get_file_as_json

log = getLogger( __name__ )

ENABLE_LIVE_TESTS = 'ENABLE_LIVE_TESTS'
PERSISTANCE_NAME = 'persistance_layer'

class Environment( NamedTuple ):
	ctx: ApplicationContext
	db: ActivityDb
	registry: Registry

def marker( request, name, key, default ):
	try:
		m = request.node.get_closest_marker( name )
		if key:
			return m.kwargs[key]
		elif not key:
			return m.args[0]
	except (AttributeError, KeyError, TypeError):
		log.error( f'unable to access marker {name}.{key}', exc_info=True )
		return default

# shared fixtures

# noinspection PyTestUnpassedFixture
@fixture
def fs( request ) -> FS:
	env = marker( request, 'context', 'env', 'empty' )
	persist = marker( request, 'context', 'persist', 'mem' )
	cleanup = marker( request, 'context', 'cleanup', True )

	with pkgpath( 'test', '__init__.py' ) as test_pkg_path:
		tp = test_pkg_path.parent
		env_fs = OSFS( root_path=f'{str( tp )}/environments/{env}' )
		ep = Path( tp, f'environments/{env}' )
		vrp = Path( tp, f'../var/run/{datetime.now().strftime( "%H%M%S_%f" )}' ).resolve()

		if persist in ['disk', 'clone']:
			vrp.mkdir( parents=True, exist_ok=True )
			root_fs = OSFS( str( vrp ), expand_vars=True )
			log.info( f'created new temporary persistance dir in {str( vrp )}' )

			if persist == 'clone':
				copytree( ep, vrp, dirs_exist_ok=True )

		elif persist == 'mem':
			root_fs = MemoryFS()
			log.info( f'using memory as root fs backend' )

			copy_fs( env_fs, root_fs, preserve_time=True )

		else:
			raise ValueError( 'value of key persist needs to be one of [mem, disk, clone]' )

	yield root_fs

	if cleanup:
		if isinstance( root_fs, OSFS ):
			sp = root_fs.getsyspath( '/' )
			if dirname( dirname( sp ) ).endswith( 'var/run' ):  # sanity check: only remove when in var/run
				rmtree( sp, ignore_errors=True )
				log.info( f'cleaned up temporary persistance dir {sp}' )

@fixture
def dbfs( request, fs: FS ) -> FS:
	return SubFS( fs, '/db' )

@fixture
def db_path( request, fs: FS ) -> Path:
	if isinstance( fs, OSFS ):
		path = Path( fs.getsyspath( DB_DIRNAME ) )
		path.mkdir( parents=True, exist_ok=True )
		yield path
	else:
		raise ValueError
	#env = marker( request, 'context', 'env', 'empty' )
	#with pkgpath( 'test', '__init__.py' ) as test_pkg_path:
	#	yield Path( test_pkg_path.parent, f'environments/{env}/db' )

@fixture
def db( request, fs: FS ) -> ActivityDb:
	if isinstance( fs, OSFS ):
		db_fs = OSFS( root_path=fs.getsyspath( DB_DIRNAME ), create=True )
	elif isinstance( fs, MemoryFS ):
		db_fs = MemoryFS()
	else:
		raise ValueError

	summary_types = marker( request, 'db', 'summary_types', [] )
	recording_types = marker( request, 'db', 'recording_types', [] )

	yield ActivityDb( fs=db_fs, summary_types=summary_types, recording_types=recording_types )
	#db_path = Path( env_fs.getsyspath( '/' ), DB_DIRNAME )
	#yield ActivityDb( path=db_path, read_only=False )

@fixture
def ctx( request, fs: FS ) -> ApplicationContext:

	json = marker( request, 'context', 'json', False )
	verbose = marker( request, 'context', 'verbose', False )
	debug = marker( request, 'context', 'debug', False )
	flags = { 'verbose': verbose, 'debug': debug, 'json': json }

	context = set_current_ctx( ApplicationContext( config_fs=fs, __kwargs__=flags ) )

	yield context

#	try:
#		db_path = db.underlay_fs.getsyspath( '' )
#		context = ApplicationContext( config_dir=dirname( dirname( db_path ) ), verbose=True )
#	except NoSysPath:
#		context = ApplicationContext( config_fs=MemoryFS(), lib_fs=MemoryFS(), db_fs=db.underlay_fs, verbose=True )

#	context.db = db  # attach db to ctx

#	yield context

#	if context.db is not None:
#		context.db.close()

@fixture
def registry( request, ctx: ApplicationContext ) -> Registry:
	resource_types = marker( request, 'resource_type', 'types', [] )

	PluginManager.init()

	yield Registry.create(
		ctx=ctx,
		keywords=PluginManager.keywords,
		normalizers=PluginManager.normalizers,
		resource_types=PluginManager.resource_types,
		importers=PluginManager.importers,
		virtual_fields=PluginManager.virtual_fields,
		setups=PluginManager.setups,
		services=PluginManager.services,
	)

@fixture
def env( request, ctx: ApplicationContext, db: ActivityDb, registry: Registry ) -> Environment:
	ctx.db = db
	ctx.registry = registry
	return Environment( ctx, db, registry )

@fixture
def json( request ) -> Optional[Dict]:
	if marker := request.node.get_closest_marker( 'db' ):
		template = marker.kwargs.get( 'template', 'empty' )
		return get_db_as_json( template )
	elif marker := request.node.get_closest_marker( 'file' ):
		return get_file_as_json( marker.args[0] )

@fixture
def path( request ) -> Optional[Path]:
	with pkgpath( 'test', '__init__.py' ) as test_path:
		return Path( test_path.parent, marker( request, 'file', None, None ) )

@fixture
def fspath( request ) -> FsPath:
	with pkgpath( 'test', '__init__.py' ) as test_path:
		return FsPath( OSFS( root_path=str( test_path.parent ), create=False ), marker( request, 'file', None, None ) )

@fixture
def service( request, env: Environment ) -> Optional[Service]:
	service_class = marker( request, 'service', 'cls', None )
	service_class_name = service_class.__name__.lower() if service_class else None
	register = marker( request, 'service', 'register', False )
	init = marker( request, 'service', 'init', False )

	service = service_class( ctx=env.ctx )

#	if init:
		# service = service_class( fs=ctx.config_fs, _configuration=ctx.config['plugins'][service_class_name], _state=ctx.state['plugins'][service_class_name] )
#		service = service_class( ctx=ctx )
#	else:
#		service = service_class( fs=fs )

	if register:
		env.registry.services[service_class_name] = service

	yield service

@fixture
def keywords() -> List[str]:
	# load keywords plugin
	return list( Registry.instance().virtual_fields.keys() )

@fixture
def rule_parser( request, ctx: ApplicationContext, registry: Registry ) -> RuleParser:

	yield RuleParser( keywords=registry.keywords, normalizers=registry.normalizers )
