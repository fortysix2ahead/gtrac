
from importlib.resources import path
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Tuple

from bottle import Bottle
from confuse import Configuration
from pytest import fixture
from yaml import SafeLoader
from yaml import load as load_yaml

from tracs.config import ApplicationConfig as cfg
from tracs.config import ApplicationConfig as state
from tracs.config import GlobalConfig
from tracs.config import KEY_PLUGINS
from tracs.db import ActivityDb
from tracs.plugins.bikecitizens import Bikecitizens
from tracs.plugins.polar import Polar
from tracs.service import Service

from .bikecitizens_server import bikecitizens_server
from .bikecitizens_server import bikecitizens_server_thread
from .helpers import clean
from .helpers import get_db_as_json
from .helpers import get_file_as_json
from .helpers import get_file_db
from .helpers import get_file_path
from .helpers import get_inmemory_db
from .helpers import var_run_path
from .polar_server import polar_server
from .polar_server import polar_server_thread
from .polar_server import TEST_BASE_URL as POLAR_TEST_BASE_URL
from .polar_server import LIVE_BASE_URL as POLAR_LIVE_BASE_URL
from .strava_server import strava_server
from .strava_server import strava_server_thread

ENABLE_LIVE_TESTS = 'ENABLE_LIVE_TESTS'

# shared fixtures

# noinspection PyUnboundLocalVariable
@fixture
def db( request ) -> ActivityDb:
	if marker := request.node.get_closest_marker( 'db' ):
		template = marker.kwargs.get( 'template' )
		lib = marker.kwargs.get( 'lib' )
		name = marker.kwargs.pop( 'name', 'db.json' )
		inmemory = marker.kwargs.pop( 'inmemory', True )
		writable = marker.kwargs.pop( 'writable', False )
		update_gc = marker.kwargs.pop( 'update_gc', False )
		cleanup = marker.kwargs.pop( 'cleanup', False )

	if inmemory:
		if lib:
			db = get_inmemory_db( lib=lib )
		else:
			db = get_inmemory_db( template=template )
	else:
		if path:
			db = get_file_db( lib=lib, writable=writable )
		else:
			db = get_file_db( template=template, writable=writable )

	if update_gc:
		GlobalConfig.db = db
		GlobalConfig.db_dir = var_run_path() if inmemory else db.path.parent
		GlobalConfig.db_file = Path( GlobalConfig.db_dir, 'db.json' ) if inmemory else db.path

	yield db

	if cleanup:
		if inmemory and update_gc:
			clean( db_dir=GlobalConfig.db_dir )
		elif not inmemory:
			clean( db_dir=db.path.parent )

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

# noinspection PyUnboundLocalVariable
@fixture
def service( request ) -> Service:
	# marker processing
	if marker := request.node.get_closest_marker( 'service' ):
		service_class, base_url = marker.args[0] if marker.args else (None, None)
		service_class = marker.kwargs.pop( 'cls' ) if 'cls' in marker.kwargs else service_class
		base_url = marker.kwargs.pop( 'url' ) if 'url' in marker.kwargs else base_url

	# old way
	if marker := request.node.get_closest_marker( 'service_config' ):
		config_file, state_file = marker.args[0] if marker.args else (None, None)
	# new way
	if marker := request.node.get_closest_marker( 'config' ):
		config_file = marker.kwargs.pop( 'config' ) if 'config' in marker.kwargs else config_file
		state_file = marker.kwargs.pop( 'state' ) if 'state' in marker.kwargs else state_file

	service_class_name = service_class.__name__.lower()

	config, state = None, None
	with path('test', '__init__.py') as test_pkg_path:
		config_path = Path(test_pkg_path.parent.parent, config_file )
		if config_path.exists():
			config = Configuration( f'test.{service_class_name}', __name__, read=False )
			config.set_file(config_path)

		state_path = Path(test_pkg_path.parent.parent, state_file )
		if state_path.exists():
			state = Configuration( f'test.{service_class_name}', __name__, read=False )
			state.set_file(state_path)

	return service_class( base_url=base_url, config=config, state=state )

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
