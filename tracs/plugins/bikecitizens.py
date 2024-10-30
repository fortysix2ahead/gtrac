from datetime import datetime, timedelta
from logging import getLogger
from re import DOTALL, match
from sys import exit as sysexit
from typing import Dict, List, Optional, Tuple, Union

from attrs import define, field
from bs4 import BeautifulSoup
from dateutil.parser import parse
from dateutil.tz import tzlocal
from fs.base import FS
from fs.path import dirname
from requests import options, Session
from rich.prompt import Prompt

from tracs.activity import Activities, Activity
from tracs.activity_types import ActivityTypes
from tracs.config import ApplicationContext, APPNAME
from tracs.pluginmgr import importer, resourcetype, service, setup
from tracs.plugins.json import DataclassFactoryHandler, JSONHandler
from tracs.resources import Resource
from tracs.service import Service

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

# data classes

@define
class Point:

	lon: float = field( default=None )
	lat: float = field( default=None )
	delta: int = field( default=None )
	ele: int = field( default=None )

@resourcetype( type=BIKECITIZENS_RECORDING_TYPE, recording=False )
@define
class BikecitizensRecording:

	points: List[Point] = field( factory=list )

@resourcetype( type=BIKECITIZENS_TYPE, summary=True )
@define
class BikecitizensActivity:

	average_speed: float = field( default=None )
	cccode: str = field( default=None )
	distance: int = field( default=None )
	duration: int = field( default=None )
	id: int = field( default=None )
	ping_points: List[str] = field( factory=list )
	postproc_cnt: int = field( default=None )
	postprocessed: bool = field( default=None )
	start_time: str = field( default=None )
	tags: List[str] = field( factory=list )
	uuid: str = field( default=None )

	@property
	def local_id( self ) -> int:
		return self.id

	@property
	def uid( self ) -> str:
		return f'{SERVICE_NAME}:{self.id}'

# resource handlers

# todo: actually we can import this, but currently there are no timestamps and it's of no better use compared to the gpx
# that's why recording is currently set to False in BikecitizensRecording (see above)
@importer
class BikecitizensRecordingImporter( JSONHandler ):

	TYPE: str = BIKECITIZENS_RECORDING_TYPE

@importer
class BikecitizensImporter( DataclassFactoryHandler ):

	TYPE: str = BIKECITIZENS_TYPE
	ACTIVITY_CLS = BikecitizensActivity

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		activity: BikecitizensActivity = resource.data
		time = parse( activity.start_time )
		duration = timedelta( seconds=activity.duration )
		return Activity(
			type = ActivityTypes.bike,
			speed = activity.average_speed,
			distance = activity.distance,
			duration = duration,
			starttime= time,
			endtime=time + duration,
			starttime_local= time.astimezone( tzlocal() ),
			endtime_local=time.astimezone( tzlocal() ) + duration,
			tags = activity.tags,
			uid=f'{SERVICE_NAME}:{activity.local_id}',
		)

# service

@service
class Bikecitizens( Service ):

	def __init__( self, **kwargs ):
		super().__init__( **{ **{'name': SERVICE_NAME, 'display_name': DISPLAY_NAME, 'base_url': BASE_URL}, **kwargs } )

		self._saved_session = kwargs.get( 'session' )
		self._user_id = kwargs.get( 'user_id' )
		self._base_url = kwargs.get( 'base_url', BASE_URL )
		self._api_url = kwargs.get( 'api_url', API_URL )

		self._api_key = None
		self._session = None

		self._importer: BikecitizensImporter = BikecitizensImporter()
		self._json_handler: JSONHandler = JSONHandler()

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

	def tracks_url( self, range_from: datetime, range_to: datetime ) -> str:
		url = self.user_tracks_url
		if range_from and range_to:
			url = f'{url}?start={range_from.strftime( "%Y-%m-%d" )}&end={ range_to.strftime( "%Y-%m-%d" ) }'
		return url

	def stats_url( self, year: int ) -> str:
		return f'{self.user_url}/stats?start={year}-01-01&end={year}-12-31'

	def url_for_id( self, local_id: Union[int, str] ) -> Optional[str]:
		return f'https://api.bikecitizens.net/api/v1/tracks/{local_id}'

	# service methods

	def supports_remote_import( self ) -> bool:
		return True

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

		if not self.config_value( 'username' ) and not self.cfg_value( 'password' ):
			log.error( f'setup not complete for {self.display_name}, consider running {APPNAME} setup' )
			sysexit( -1 )

		data = {
			'utf8': '✓',
			'authenticity_token': token,
			'user[login]': self.config_value( 'username' ),
			'user[password]': self.config_value( 'password' ),
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

	def import_from_remote( self, dst_fs: FS, **kwargs ) -> Activities:
		if not self.login():
			return Activities()

		range_from = kwargs.get( 'range_from' )
		range_to = kwargs.get( 'range_to' )

		# start fetch task
		self.ctx.start( f'fetching activity data from {self.display_name}' )

		activities = Activities()

		try:
			url = self.tracks_url( range_from=range_from, range_to=range_to )
			response = options( url=url, headers=HEADERS_OPTIONS )
			json_list = self._json_handler.load( url=url, headers={ **HEADERS_OPTIONS, **{ 'X-API-Key': self._api_key } }, session=self._session )
			log.debug( f'fetched {len( json_list.data )} from service {self.display_name}' )

			for j in json_list.data:
				uid = f'{self.name}:{j.get( "id" )}'
				path = f'{self.path_for_id( j.get( "id" ), self.name )}/{j.get( "id" )}.json'

				if self.ctx.force or not self.db.contains_resource( uid, path ):
					# summary
					summary = Resource(
						content=self._json_handler.save_raw( j ),
						raw=j,
						data=self._importer.load_data( j ),
						uid=uid,
						path=path,
						type=BIKECITIZENS_TYPE,
					)

					# point list
					log.debug( f'downloading point list for {summary.uid.to_str()}' )

					url = f'{self.url_for_id( summary.local_id )}/points'
					response = options( url, headers=HEADERS_OPTIONS )
					response = self._session.get( url, headers={ **HEADERS_OPTIONS, **{ 'X-API-Key': self._api_key } } )
					point_list = Resource(
						content=response.content,
						path=f'{summary.path[0:-4]}rec.json',
						source=url,
						text=response.text,
						type=BIKECITIZENS_RECORDING_TYPE,
						uid=summary.uid,
					)

					# gpx recording
					log.debug( f'downloading GPX recording for {summary.uid.to_str()}' )

					url = f'{self.url_for_id( summary.local_id )}/gpx'
					response = options( url, headers=HEADERS_OPTIONS )
					response = self._session.get( url, headers={ **HEADERS_OPTIONS, **{ 'X-API-Key': self._api_key } } )
					recording = Resource(
						content=response.content,
						path=f'{summary.path[0:-4]}gpx',
						source=url,
						text=response.text,
						type=BIKECITIZENS_RECORDING_TYPE,
						uid=summary.uid,
					)

					dst_fs.makedirs( dirname( path ), recreate=True )
					dst_fs.writebytes( summary.path, contents=summary.content )
					dst_fs.writebytes( point_list.path, contents=point_list.content )
					dst_fs.writebytes( recording.path, contents=recording.content )
					log.debug( f'wrote summary, point list and recording to {dst_fs}/{summary.path}, {point_list.path}, {recording.path}' )

					# create activity and unload resources
					ride = self._importer.load_as_activity( resource=summary )
					ride.resources.extend( [ point_list, recording ] )
					summary.unload()
					point_list.unload()
					recording.unload()
					activities.append( ride )

		except RuntimeError:
			log.error( f'error fetching summaries', exc_info=True )

		return activities

# plugin setup

INTRO = f'For Bikecitizens we will use their Web API to download activity data, that\'s why your credentials are needed.'

@setup
def setup( ctx: ApplicationContext, config: Dict, state: Dict ) -> Tuple[Dict, Dict]:
	ctx.console.print( INTRO, width=120 )

	user = Prompt.ask( 'Enter your user name', console=ctx.console, default=config.get( 'username', '' ) )
	password = Prompt.ask( 'Enter your password', console=ctx.console, default=config.get( 'password' ), password=True )

	return { 'username': user, 'password': password }, {}
