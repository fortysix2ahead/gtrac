from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta
from logging import getLogger
from re import DOTALL
from re import match
from sys import exit as sysexit
from typing import Any
from typing import cast
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from bs4 import BeautifulSoup
from dateutil.parser import parse
from dateutil.tz import tzlocal
from requests import options
from requests import Session
from rich.prompt import Prompt

from .gpx import GPX_TYPE
from .handlers import JSON_TYPE
from .handlers import JSONHandler
from ..activity import Activity
from ..activity_types import ActivityTypes
from ..config import ApplicationContext
from ..config import APPNAME
from ..config import console
from ..plugin import Plugin
from ..registry import importer
from ..registry import Registry
from ..registry import resourcetype
from ..registry import service
from ..resources import Resource
from ..service import Service
from ..utils import seconds_to_time

log = getLogger( __name__ )

SERVICE_NAME = 'bikecitizens'
DISPLAY_NAME = 'Bike Citizens'

BASE_URL = 'https://my.bikecitizens.net'
API_URL = 'https://api.bikecitizens.net'

BIKECITIZENS_TYPE = 'application/vnd.bikecitizens+json'
BIKECITIZENS_RECORDING_TYPE = 'application/vnd.bikecitizens.rec+json'

HEADERS_TEMPLATE = {
	'Accept-Encoding': 'gzip, deflate, br',
	'Accept-Language': 'en-US,en;q=0.5',
	'Cache-Control': 'no-cache',
	'Connection': 'keep-alive',
	'DNT': '1',
	'Pragma': 'no-cache',
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0'
}

HEADERS_LOGIN = { **HEADERS_TEMPLATE, **{
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
		'Content-Type': 'application/x-www-form-urlencoded',
		'Host': 'my.bikecitizens.net',
		'Origin': 'https://my.bikecitizens.net',
		'Referer': 'https://my.bikecitizens.net/users/sign_in',
		'TE': 'Trailers',
	}
}

HEADERS_OPTIONS = { **HEADERS_TEMPLATE, **{
		'Accept': '*/*',
		'Access-Control-Request-Method': 'GET',
		'Access-Control-Request-Headers': 'x-api-key',
		'Host': 'api.bikecitizens.net',
		'Referer': 'https://my.bikecitizens.net/',
		'Origin': 'https://my.bikecitizens.net',
		'Sec-Fetch-Dest': 'empty',
		'Sec-Fetch-Mode': 'cors',
		'Sec-Fetch-Site': 'same-site'
	}
}

@resourcetype( type=BIKECITIZENS_TYPE, summary=True )
@dataclass
class BikecitizensActivity:

	id: int = field( default=None )
	average_speed: float = field( default=None )
	distance: int = field( default=None )
	duration: int = field( default=None )
	start_time: str = field( default=None )
	postprocessed: bool = field( default=None )
	postproc_cnt: int = field( default=None )
	uuid: str = field( default=None )
	cccode: str = field( default=None )
	tags: List[str] = field( default_factory=list )
	ping_points: List[str] = field( default_factory=list )

	@property
	def local_id( self ) -> int:
		return self.id

	def as_activity( self ) -> Activity:
		time = parse( self.start_time )
		duration = seconds_to_time( self.duration )
		return Activity(
			type = ActivityTypes.bike,
			speed = self.average_speed,
			distance = self.distance,
			duration = duration,
			time = time,
			time_end = time + timedelta( hours=duration.hour, minutes=duration.minute, seconds=duration.second ),
			localtime = time.astimezone( tzlocal() ),
			localtime_end = time.astimezone( tzlocal() ) + timedelta( hours=duration.hour, minutes=duration.minute, seconds=duration.second ),
			tags = self.tags,
			uids=[f'{SERVICE_NAME}:{self.local_id}'],
		)

@importer( type=BIKECITIZENS_TYPE )
class BikecitizensImporter( JSONHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=BIKECITIZENS_TYPE, activity_cls=BikecitizensActivity )

@service
class Bikecitizens( Service, Plugin ):

	def __init__( self, **kwargs ):
		super().__init__( name=SERVICE_NAME, display_name=DISPLAY_NAME, **kwargs )

		self._username = kwargs.get( 'username' )
		self._password = kwargs.get( 'password' )

		self._base_url = kwargs.get( 'base_url', BASE_URL )
		self._saved_session = kwargs.get( 'session' )
		self._user_id = kwargs.get( 'user_id' )
		self._api_url = kwargs.get( 'api_url', API_URL )

		self._api_key = None
		self._session = None

		self.importer: BikecitizensImporter = cast( BikecitizensImporter, Registry.importer_for( BIKECITIZENS_TYPE ) )
		self.json_handler: JSONHandler = cast( JSONHandler, Registry.importer_for( JSON_TYPE ) )

	@property
	def api_url( self ) -> str:
		return self._api_url

	@property
	def signin_url( self ):
		return f'{self.base_url}/users/sign_in'

	@property
	def user_url( self ) -> str:
		return f'{self._api_url}/api/v1/users/{self._user_id}'

	@property
	def user_tracks_url( self ) -> str:
		return f'{self._api_url}/api/v1/tracks/user/{self._user_id}'

	# sample: https://api.bikecitizens.net/api/v1/users/{user_id}/stats?start=2010-01-01&end=2022-12-31
	def stats_url( self, year: int ) -> str:
		return f'{self.user_url}/stats?start={year}-01-01&end={year}-12-31'

	# service methods

	def login( self ) -> bool:
		if self.logged_in and self._session:
			return self.logged_in

		if not self._session:
			self._session = Session()

		# session restore does not yet work
		#		if self.name in self._state:
		#			self._session.cookies.set( "api_key", self._state[self.name]['api_key'], domain="my.bikecitizens.net" )
		#			self._session.cookies.set( "_dashboard_session", self._state[self.name]['session'], domain="my.bikecitizens.net" )
		#			return True

		response = self._session.get( self.signin_url )

		try:
			token = BeautifulSoup( response.text, 'html.parser' ).find( 'input', attrs={ 'name': 'authenticity_token' } )['value']
		except TypeError:
			token = None

		if token is None:
			log.error( f"Unable to find authenticity token for {self.name}" )
			return False
		else:
			log.debug( f"Found authenticity token for {self.name}: {token}" )

		if not self._username and not self._password:
			log.error( f'setup not complete for {self.display_name}, consider running {APPNAME} setup' )
			sysexit( -1 )

		data = {
			'utf8': '✓',
			'authenticity_token': token,
			'user[login]': self._username,
			'user[password]': self._password,
			'commit': 'Login'
		}

		response = self._session.post( self.signin_url, headers=HEADERS_LOGIN, data=data )

		# status should be 200, need to check what is returned if credentials are wrong
		if response.status_code == 200:
			self.set_state_value( 'session', self._session.cookies['_dashboard_session'] )
			self.set_state_value( 'api_key', self._session.cookies['api_key'] )
		else:
			log.error( f'Login to {self.name} failed' )
			return False

		response = self._session.get( self.base_url )

		try:
			scripts = BeautifulSoup( response.text, 'html.parser' ).find_all( 'script' )
			for script in scripts:
				if m := match( r'.*\"id\":\s*\"(\d*)\".*', script.text, flags=DOTALL ):
					self._user_id = int( m.group( 1 ) )
					self.set_state_value( 'user_id', self._user_id )
		except TypeError:
			pass

		if 'api_key' in self._session.cookies:
			self._api_key = self._session.cookies['api_key']
		else:
			log.error( f'Unable to find api key for {self.name}' )
			return False

		if self._user_id is None:
			log.error( f'Unable to find user id for {self.name}' )
			return False

		self._logged_in = True
		return self._logged_in

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		if not self.login():
			return []

		try:
			response = options( url=self.user_tracks_url, headers=HEADERS_OPTIONS )
			json_resource = self.json_handler.load( url=self.user_tracks_url, headers={ **HEADERS_OPTIONS, **{ 'X-API-Key': self._api_key } }, session=self._session )

			resources: List[Resource] = []
			for item in json_resource.raw:
				resources.append( self.importer.save( item, uid = f'{self.name}:{item["id"]}', resource_path=f'{item["id"]}.json', resource_type=BIKECITIZENS_TYPE, status = 200, summary = True ) )

			return resources

		except RuntimeError:
			log.error( f'error fetching activity ids', exc_info=True )
			return []

	def download( self, summary: Resource = None, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		resources = [
			Resource( uid=summary.uid, path=f'{summary.local_id}.rec.json', type=BIKECITIZENS_RECORDING_TYPE, source=f'{self.url_for_id( summary.local_id )}/points' ),
			Resource( uid=summary.uid, path=f'{summary.local_id}.gpx', type=GPX_TYPE, source=f'{self.url_for_id( summary.local_id )}/gpx' )
		]

		for r in resources:
			if not summary.get_child( r.type ) or force:
				try:
					self.download_resource( r )
				except RuntimeError:
					log.error( f'error fetching resource from {r.source}', exc_info=True )

		return [ r for r in resources if r.content ]

	def download_resource( self, resource: Resource, **kwargs ) -> Tuple[Any, int]:
		log.debug( f'downloading resource from {resource.source}' )
		# noinspection PyUnusedLocal
		response = options( resource.source, headers=HEADERS_OPTIONS )
		response = self._session.get( resource.source, headers={ **HEADERS_OPTIONS, **{ 'X-API-Key': self._api_key } } )
		resource.content, resource.text, resource.status = response.content, response.text, response.status_code
		return response.content, response.status_code

	def url_for_id( self, local_id: Union[int, str] ) -> Optional[str]:
		return f'https://api.bikecitizens.net/api/v1/tracks/{local_id}'

	def url_for_resource_type( self, local_id: Union[int, str], type: str ) -> Optional[str]:
		url = None

		if type == GPX_TYPE:
			url = f'{self.url_for_id( local_id )}/gpx'
		elif type == BIKECITIZENS_RECORDING_TYPE:
			url = f'{self.url_for_id( local_id )}/points'

		return url

	def setup( self, ctx: ApplicationContext ) -> None:
		console.print( f'For Bikecitizens we will use their Web API to download activity data, that\'s why your credentials are needed.' )

		user = Prompt.ask( 'Enter your user name', default=self.cfg_value( 'username' ) or '' )
		pwd = Prompt.ask( 'Enter your password', default=self.cfg_value( 'password' ) or '', password=True )

		self.set_cfg_value( 'username', user )
		self.set_cfg_value( 'password', pwd )

	def setup_complete( self ) -> bool:
		pass
