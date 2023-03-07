
from importlib.resources import path as resource_path
from logging import getLogger
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Tuple

from bottle import Bottle
from confuse import ConfigReadError
from confuse import Configuration
from pytest import fixture
from yaml import SafeLoader
from yaml import load as load_yaml

from tracs.config import ApplicationConfig as cfg
from tracs.config import ApplicationConfig as state
from tracs.config import ApplicationContext
from tracs.config import KEY_PLUGINS
from tracs.db import ActivityDb
from tracs.registry import Registry
from tracs.plugins.bikecitizens import Bikecitizens
from tracs.plugins.polar import Polar
from tracs.service import Service

from .bikecitizens_server import bikecitizens_server
from .bikecitizens_server import bikecitizens_server_thread
from .helpers import cleanup as cleanup_path, get_db
from .helpers import get_db_as_json
from .helpers import get_file_as_json
from .helpers import get_file_db
from .helpers import get_file_path
from .helpers import get_inmemory_db
from .helpers import prepare_context
from .polar_server import polar_server
from .polar_server import polar_server_thread
from .polar_server import TEST_BASE_URL as POLAR_TEST_BASE_URL
from .polar_server import LIVE_BASE_URL as POLAR_LIVE_BASE_URL
from .strava_server import strava_server
from .strava_server import strava_server_thread

log = getLogger( __name__ )

ENABLE_LIVE_TESTS = 'ENABLE_LIVE_TESTS'

# shared fixtures

@fixture
def db( request ) -> ActivityDb:
	if marker := request.node.get_closest_marker( 'db' ):
		template = marker.kwargs.get( 'template' )
		library_template = marker.kwargs.get( 'library' )
		read_only = marker.kwargs.get( 'read_only', True )
		cleanup = marker.kwargs.get( 'cleanup', True )
	else:
		return None

	db = get_db( template=template, read_only=read_only )

	# set base path in services
	if library_template:
		for name, instance in Registry.services.items():
			# noinspection PyPropertyAccess
			instance.base_path = Path( db.path, name )

	yield db

	if cleanup and not read_only:
		cleanup_path( db.path )

@fixture
def config( request ) -> None:
	if marker := request.node.get_closest_marker( 'config' ):
		template = marker.kwargs.get( 'template' )
		writable = marker.kwargs.get( 'writable', False )
		cleanup = marker.kwargs.get( 'cleanup', True )
	else:
		return None

@fixture
def ctx( request ) -> Optional[ApplicationContext]:
	try:
		marker = request.node.get_closest_marker( 'context' )
		lib_template = marker.kwargs.get( 'library' )
		cfg_template = marker.kwargs.get( 'config' )
		do_cleanup = marker.kwargs.get( 'cleanup' )

		context: ApplicationContext = prepare_context( cfg_template, lib_template )

		yield context

		context.db.close()

		if do_cleanup:
			cleanup_path( context.cfg_dir )

	except ValueError:
		log.error( 'unable to run fixture context', exc_info=True )

@fixture
def json( request ) -> Optional[Dict]:
	if marker := request.node.get_closest_marker( 'db' ):
		template = marker.kwargs.get( 'template', 'empty' )
		return get_db_as_json( template )
	elif marker := request.node.get_closest_marker( 'file' ):
		return get_file_as_json( marker.args[0] )

@fixture
def path( request ) -> Optional[Path]:
	if marker := request.node.get_closest_marker( 'file' ):
		return get_file_path( marker.args[0] )

@fixture
def config_state( request ) -> Optional[Tuple[Dict, Dict]]:
	config_dict, state_dict = None, None

	if config_marker := request.node.get_closest_marker( 'config_file' ):
		with path( 'test', '__init__.py' ) as test_pkg_path:
			config_path = Path( test_pkg_path.parent.parent, 'var', config_marker.args[0] )
			if config_path.exists():
				cfg.set_file( config_path )
				config_dict = load_yaml( config_path.read_bytes(), SafeLoader )

	if state_marker := request.node.get_closest_marker( 'state_file' ):
		with path( 'test', '__init__.py' ) as test_pkg_path:
			state_path = Path( test_pkg_path.parent.parent, 'var', state_marker.args[0] )
			if state_path.exists():
				state.set_file( state_path )
				state_dict = load_yaml( state_path.read_bytes(), SafeLoader )

	return config_dict, state_dict

@fixture
def service( request, ctx ) -> Optional[Service]:
	try:
		marker = request.node.get_closest_marker( 'service' )
		service_class = marker.kwargs.get( 'cls' )
		service_class_name = service_class.__name__.lower()
		base_url = marker.kwargs.get( 'url' )

		if ctx:
			service_config = ctx.cfg_file
			service_state = ctx.state_file
		else:
			service_config = marker.kwargs.get( 'config' )
			service_state = marker.kwargs.get( 'state' )

		with resource_path( 'test', '__init__.py' ) as test_pkg_path:
			try:
				config_path = Path( test_pkg_path.parent.parent, service_config )
				config = Configuration( f'test.{service_class_name}', __name__, read=False )
				config.set_file( config_path )
				ctx.config = config
			except ConfigReadError:
				pass

			try:
				state_path = Path( test_pkg_path.parent.parent, service_state )
				state = Configuration( f'test.{service_class_name}', __name__, read=False )
				state.set_file( state_path )
				ctx.state = state
			except ConfigReadError:
				pass

			s = service_class( ctx=ctx, base_url=base_url, base_path=Path( ctx.db_dir, service_class_name ), config=config, state=state, **marker.kwargs )
			Registry.services[s.name] = s
			return s

	except ValueError:
		log.error( 'unable to run fixture service', exc_info=True )

# bikecitizens specific fixtures

@fixture
def bikecitizens_server() -> Bottle:
	if not bikecitizens_server_thread.is_alive():
		bikecitizens_server_thread.start()
	return bikecitizens_server

@fixture
def bikecitizens_service( request ) -> Optional[Bikecitizens]:
	if marker := request.node.get_closest_marker( 'base_url' ):
		service = Bikecitizens()
		service.base_url = marker.args[0]
		return service
	return None

# polar specific fixtures

@fixture
def polar_server() -> Bottle:
	if not polar_server_thread.is_alive():
		polar_server_thread.start()
	return polar_server

@fixture
def polar_service( request ) -> Optional[Polar]:
	if marker := request.node.get_closest_marker( 'base_url' ):
		service = Polar()
		service.base_url = marker.args[0]
		return service
	return None

@fixture
def polar_test_service() -> Polar:
	polar = Polar()
	polar.base_url = POLAR_TEST_BASE_URL

	cfg[KEY_PLUGINS]['polar']['username'] = 'sample user'
	cfg[KEY_PLUGINS]['polar']['password'] = 'sample password'

	return polar

@fixture
def polar_live_service() -> Polar:
	polar = Polar()
	polar.base_url = POLAR_LIVE_BASE_URL
	return polar

# strava specific fixtures

@fixture
def strava_server() -> Bottle:
	if not strava_server_thread.is_alive():
		strava_server_thread.start()
	return strava_server
