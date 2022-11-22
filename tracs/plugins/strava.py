
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from re import findall
from re import match
from typing import Any
from typing import cast
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from bs4 import BeautifulSoup
from click import echo
from datetime import datetime
from dateutil.tz import UTC
from logging import getLogger
from oauthlib.oauth2 import InvalidGrantError # package name is not oauthlib
from pathlib import Path
from requests import Session
from requests_oauthlib import OAuth2Session
from sys import exit as sysexit
from webbrowser import open as open_url

from rich.prompt import Prompt

from ..registry import Registry
from ..registry import document
from ..registry import importer
from ..registry import resourcetype
from ..registry import service
from .gpx import GPX_TYPE
from .fit import FIT_TYPE
from .handlers import JSON_TYPE
from .handlers import JSONHandler
from .handlers import TCX_TYPE
from ..plugin import Plugin
from ..activity import Activity
from ..resources import Resource
from ..activity_types import ActivityTypes
from ..activity_types import ActivityTypes as Types
from ..config import ApplicationContext
from ..config import console
from ..config import APPNAME
from ..service import Service
from ..utils import seconds_to_time as stt
from ..utils import to_isotime

log = getLogger( __name__ )

SERVICE_NAME = 'strava'
DISPLAY_NAME = 'Strava'

STRAVA_TYPE = 'application/vnd.strava+json'

BASE_URL = 'https://www.strava.com'
OAUTH_REDIRECT_URL = 'http://localhost:40004'

FETCH_PAGE_SIZE = 200 # maximum possible size?

HEADERS_TEMPLATE = {
}

HEADERS_LOGIN = { **HEADERS_TEMPLATE, **{
	'Accept': '*/*',
	'Accept-Encoding': 'gzip, deflate, br',
	'Accept-Language': 'en-US,en;q=0.5',
	'Cache-Control': 'no-cache',
	'Connection': 'keep-alive',
	'Content-Type': 'application/x-www-form-urlencoded',
	'DNT': '1',
	'Host': 'www.strava.com',
	'Origin': 'https://www.strava.com',
	'Pragma': 'no-cache',
	'Referer': 'https://www.strava.com/login',
	'TE': 'Trailers',
	'Upgrade-Insecure-Requests': '1',
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
} }

TYPES = {
	'AlpineSki': Types.ski,
	'BackcountrySki': Types.xcski_backcountry,
	'Canoeing': Types.canoe,
	'Crossfit': Types.crossfit,
	'EBikeRide': Types.bike_ebike,
	'Elliptical': Types.other,
	'Golf': Types.golf,
	'Handcycle': Types.bike_hand,
	'Hike': Types.hike,
	'IceSkate': Types.ice_skate,
	'InlineSkate': Types.inline_skate,
	'Kayaking': Types.kayak,
	'Kitesurf': Types.kitesurf,
	'NordicSki': Types.xcski,
	'Ride': Types.bike,
	'RockClimbing': Types.climb,
	'RollerSki': Types.rollski,
	'Rowing': Types.row,
	'Run': Types.run,
	'Sail': Types.sail,
	'Skateboard': Types.skateboard,
	'Snowboard': Types.snowboard,
	'Snowshoe': Types.snowshoe,
	'Soccer': Types.soccer,
	'StairStepper': Types.other,
	'StandUpPaddling': Types.paddle_standup,
	'Surfing': Types.surf,
	'Swim': Types.swim,
	'Velomobile': Types.other,
	'VirtualRide': Types.bike_ergo,
	'VirtualRun': Types.run_ergo,
	'Walk': Types.walk,
	'WeightTraining': Types.gym,
	'Wheelchair': Types.other,
	'Windsurf': Types.surf_wind,
	'Workout': Types.gym,
	'Yoga': Types.yoga,
}

@resourcetype( type=STRAVA_TYPE, summary=True )
class StravaActivity( Activity ):

	def __raw_init__( self, raw: Any ) -> None:
		self.raw_id = self.raw.get( 'id', 0 )
		self.name = self.raw.get( 'name' )
		self.type = TYPES.get( self.raw.get( 'type' ), ActivityTypes.unknown )
		self.time = to_isotime( self.raw.get( 'start_date' ) )
		self.localtime = to_isotime( self.raw.get( 'start_date_local' ) )
		self.distance = self.raw.get( 'distance' )
		self.speed = self.raw.get( 'average_speed' )
		self.speed_max = self.raw.get( 'max_speed' )
		self.ascent = self.raw.get( 'total_elevation_gain' )
		self.descent = self.raw.get( 'total_elevation_gain' )
		self.elevation_max = self.raw.get( 'elev_high' )
		self.elevation_min = self.raw.get( 'elev_low' )
		self.duration = stt( self.raw.get( 'elapsed_time' ) ) if self.raw.get( 'elapsed_time' ) else None
		self.duration_moving = stt( self.raw.get( 'moving_time' ) ) if self.raw.get( 'moving_time' ) else None
		self.heartrate = float( self.raw.get( 'average_heartrate' ) ) if self.raw.get( 'average_heartrate' ) else None
		self.heartrate_max = float( self.raw.get( 'max_heartrate' ) ) if self.raw.get( 'max_heartrate' ) else None
		self.location_country = self.raw.get( 'location_country' )

		self.classifier = f'{SERVICE_NAME}'
		self.uid = f'{self.classifier}:{self.raw_id}'

@importer( type=STRAVA_TYPE )
class StravaImporter( JSONHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=STRAVA_TYPE, activity_cls=StravaActivity )

@service
class Strava( Service, Plugin ):

	def __init__( self, base_url=None, **kwargs ):
		super().__init__( name=SERVICE_NAME, display_name=DISPLAY_NAME, **kwargs )
		self.base_url = base_url
		self.importer: StravaImporter = cast( StravaImporter, Registry.importer_for( STRAVA_TYPE ) )
		self.json_handler: JSONHandler = cast( JSONHandler, Registry.importer_for( JSON_TYPE ) )

	@property
	def base_url( self ) -> str:
		return self._base_url

	@base_url.setter
	def base_url( self, url: str ) -> None:
		self._base_url = url if url else BASE_URL
		self._login_url = f'{self.base_url}/login'
		self._session_url = f'{self.base_url}/session'
		self._activities_url = f'{self.base_url}/activities'
		self._auth_url = f'{self.base_url}/oauth/authorize'
		self._token_url = f'{self.base_url}/oauth/token'
		self._scope = 'activity:read_all'
		self._redirect_url = OAUTH_REDIRECT_URL
		self._session = None
		self._oauth_session = None

	def url_events_year( self, year, page: int ) -> str:
		after = int( datetime( year, 1, 1, tzinfo=UTC ).timestamp() )
		before = int( datetime( year + 1, 1, 1, tzinfo=UTC ).timestamp() )
		per_page = FETCH_PAGE_SIZE # we might make this configurable later ...
		return f'{self._base_url}/api/v3/athlete/activities?before={before}&after={after}&page={page}&per_page={per_page}'

	def all_events_url( self, page: int ) -> str:
		after = int( datetime( 1970, 1, 1, tzinfo=UTC ).timestamp() )
		before = int( datetime( datetime.utcnow().year + 1, 1, 1, tzinfo=UTC ).timestamp() )
		per_page = FETCH_PAGE_SIZE  # we might make this configurable later ...
		return f'{self._base_url}/api/v3/athlete/activities?before={before}&after={after}&page={page}&per_page={per_page}'

	def url_for_id( self, local_id: Union[int, str] ) -> Optional[str]:
		return f'{self._activities_url}/{local_id}'

	def url_for_resource_type( self, local_id: Union[int, str], type: str ) -> Optional[str]:
		if type == GPX_TYPE:
			return f'{self._activities_url}/{local_id}/export_gpx'
		elif type == TCX_TYPE:
			return f'{self._activities_url}/{local_id}/export_original'

	def _link_path( self, activity: Activity, ext: str ) -> Path or None:
		#		if activity.id:
		utc = activity.utctime
		parent = Path( self._lib_dir, utc.strftime( '%Y/%m/%d' ) )
		#			a = self.db.get_activity( activity )
		#			if a and a.name:
		#				return Path( parent, f'{utc.strftime( "%H%M%S" )} - {a.name}.strava.{ext}' )  # fully qualified path
		#			else:
		return Path( parent, f'{utc.strftime( "%H%M%S" )}.{self.name}.{ext}' )  # fully qualified path

	def weblogin( self ):
		if not self._session:
			self._session = Session()
			response = self._session.get( self._login_url )

			try:
				token = BeautifulSoup( response.text, 'html.parser' ).find( 'meta', attrs={'name': 'csrf-token'} )['content']
			except TypeError:
				token = None

			log.debug( f"CSRF Token: {token}" )

			if token is None:
				echo( "CSRF Token not found" )
				return None

			if not self.cfg_value( 'username' ) and not self.cfg_value( 'password' ):
				log.error( f"application setup not complete for Strava, consider running {APPNAME} setup --strava" )
				sysexit( -1 )

			data = {
				'utf8': '✓',
				'authenticity_token': token,
				'plan': '',
				'email': self.cfg_value( 'username' ),
				'password': self.cfg_value( 'password' )
			}
			response = self._session.post( self._session_url, headers=HEADERS_LOGIN, data=data )

			if not response.status_code == 200:
				log.error( "web login failed for Strava, are the credentials correct?" )

	def login( self ):
		# check if access token is available
		if not self.state_value( 'access_token' ):
			log.error( f"application setup not complete for Strava, consider running {APPNAME} setup --strava" )
			sysexit( -1 )

		client_id = self.cfg_value( 'client_id' )
		token = self._oauth_token()
		extra = {
			'client_id': client_id,
			'client_secret': self.cfg_value( 'client_secret' )
		}

		self._oauth_session = OAuth2Session( client_id, token=token, auto_refresh_url=self._token_url, auto_refresh_kwargs = extra, token_updater = self._save_oauth_token )

		# do web login as well
		self.weblogin()

		# todo: how to detect unsuccessful login?
		if self._oauth_session and self._session:
			return True

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		if not self.login():
			return []

		self.ctx.start( f'fetching activity summaries from {self.display_name}' )

		try:
			resources = []
			for page in range( 1, 999999 ):
				self.ctx.advance( f'activities {(page - 1) * FETCH_PAGE_SIZE} to { page * FETCH_PAGE_SIZE } (page {page})' )

				# status is 429 and raw['message'] = 'Rate Limit Exceeded', when rate goes out of bounds ...
				json_resource = self.json_handler.load( url=self.all_events_url( page ), session=self._oauth_session )

				for item in json_resource.raw:
					resources.append( self.importer.save( item, uid=f"{self.name}:{item['id']}", resource_path=f"{item['id']}.json", resource_type=STRAVA_TYPE, status=200, source=self.url_for_id( item['id'] ), summary=True ) )

				if not json_resource.raw or len( json_resource.raw ) == 0:
					break

			self.ctx.complete( 'done' )

			return resources

		except RuntimeError:
			log.error( f'error fetching activity ids', exc_info=True )
			return []

	def download( self, activity: Optional[Activity] = None, summary: Optional[Resource] = None, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		try:
			urls = [ f'{self._activities_url}/{summary.raw_id}/export_gpx', f'{self._activities_url}/{summary.raw_id}/export_original' ]
			resources = [ Resource( uid=summary.uid, source=url ) for url in urls ]

			for r in resources:
				self.download_resource( r )

			summary.resources.extend( resources )

			return resources

		except RuntimeError:
			log.error( f'error fetching resources', exc_info=True )
			return []

	def download_resource( self, resource: Resource, **kwargs ) -> Tuple[Any, int]:
		if url := resource.source:
			log.debug( f'downloading resource from {url}' )
			response = self._session.get( url, headers=HEADERS_LOGIN, allow_redirects=True, stream=True )

			# content type is 'text/html; charset=utf-8' for .gpx resources that do not exist (i.e. for strenth training)
			# disposition is None in such cases
			content_type = response.headers.get( 'Content-Type' )
			content_disposition = response.headers.get( 'content-disposition' )

			ext = findall( r'^.*filename=\".+\.(\w+)\".*$', response.headers['content-disposition'] )[0]
			resource_type = Registry.resource_type_for_suffix( ext )
			resource.content = response.content
			resource.type = resource_type
			resource.path = f'{resource.local_id}.{ext}'
			resource.status = response.status_code

			# fit is binary, there's no text version to be stored
			if resource_type == FIT_TYPE:
				resource.text = None

			# fix for Strava bug where TCX documents contain whitespace before the first XML tag
			# sample first line:
			# '          <?xml version="1.0" encoding="UTF-8"?><TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"> ...'
			if resource.type == TCX_TYPE:
				if resource.text:
					resource.text = resource.text.lstrip( ' ' )
				if resource.content:
					while resource.content[0:1] == b' ':
						resource.content = resource.content[1:]

			return response.content, response.status_code
		else:
			log.warning( f'unable to determine download url for resource {resource}' )
			return None, 500

	@property
	def logged_in( self ) -> bool:
		return True if self._session and self._oauth_session else False

	def _oauth_token( self ) -> dict:
		return {
			'access_token': self.state_value( 'access_token' ),
			'refresh_token': self.state_value( 'refresh_token' ),
			'token_type': self.state_value( 'token_type' ),
			'expires_at': self.state_value( 'expires_at' ),
			'expires_in': int( self.state_value( 'expires_at' ) - datetime.utcnow().timestamp() )
		}

	def _save_oauth_token( self, token: dict ) -> None:
		self.set_state_value( 'access_token', token['access_token'] )
		self.set_state_value( 'refresh_token', token['refresh_token'] )
		self.set_state_value( 'token_type', token['token_type'] )
		self.set_state_value( 'expires_at', int( token['expires_at'] ) )
		self.set_state_value( 'expires_in', token['expires_in'] )

	def setup( self, ctx: ApplicationContext ) -> None:
		console.print( f'GPX and TCX files from Strava will be downloaded via Strava\'s Web API, that\'s why your credentials are needed.' )

		user = Prompt.ask( 'Enter your user name', default=self.cfg_value( 'username' ) or '' )
		pwd = Prompt.ask( 'Enter your password', default=self.cfg_value( 'password' ) or '', password=True )

		console.print()

		# https://developers.strava.com/docs/authentication/
		client_id_text = 'Checking for new activities and downloading photos works by using Strava\'s REST API. To be able ' \
		                 'to use this API you need to enter your Client ID and your Client Secret. In order to retrieve both, ' \
		                 'you need to create your own Strava application. Head to https://www.strava.com/settings/api ' \
		                 'and enter all necessary details. Once you created your application, the ID and the secret ' \
		                 'will be displayed.'
		console.print( client_id_text, soft_wrap=True )

		client_id = Prompt.ask( 'Enter your Client ID', default=str( self.cfg_value( 'client_id' ) or '' ) )
		client_secret = Prompt.ask( 'Enter your Client Secret', default=self.cfg_value( 'client_secret' ) or '' )

		console.print()

		oauth = OAuth2Session( client_id, redirect_uri=self._redirect_url, scope=[self._scope] )
		auth_url, auth_state = oauth.authorization_url( self._auth_url )

		client_code_text = f'For the next step we need to obtain the Client Code. This code can be obtained by visiting this ' \
		                   f'URL: {auth_url} After authorizing {APPNAME} you will be redirected to {self._redirect_url} and the ' \
		                   f'code is part of the URL displayed in your browser. Have a look at the displayed ' \
		                   f'URL: {self._redirect_url}?code=<CLIENT_CODE_IS_DISPLAYED_HERE>&scope={self._scope}'
		console.print( client_code_text, soft_wrap=True )
		client_code = Prompt.ask( 'Enter your Client Code or press enter to open the link in your browser.' )

		if not client_code:
			open_url( auth_url )
			webServer = HTTPServer( ( 'localhost', 40004), StravaSetupServer )

			try:
				webServer.serve_forever()
			except KeyboardInterrupt:
				pass

			client_code = StravaSetupServer.client_code
			webServer.server_close()

		try:
			# save user/password
			self.set_cfg_value( 'username', user )
			self.set_cfg_value( 'password', pwd )
			self.set_cfg_value( 'client_code', client_code )
			self.set_cfg_value( 'client_id', client_id )
			self.set_cfg_value( 'client_secret', client_secret )

			# save oauth tokens
			token = oauth.fetch_token( self._token_url, code=client_code, client_secret=client_secret, include_client_id=True )
			self._save_oauth_token( token )
			log.debug( f"fetched access token {token['access_token']} and refresh_token {token['refresh_token']}, expiring at {token['expires_at']}" )
		except InvalidGrantError:
			console.print( f'Error: authorization not granted.' )
			return

	def setup_complete( self ) -> bool:
		pass

class StravaSetupServer( BaseHTTPRequestHandler ):

	client_code = None

	def do_GET(self):
		if m := match( '^.+code=([\da-f]+).*$', self.path ):
			StravaSetupServer.client_code = m[1]
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write(bytes("<html><head><title></title></head>", "utf-8"))
		if m[1]:
			self.wfile.write(bytes("<body><p>Client code successfully detected.</p></body>", "utf-8"))
		else:
			self.wfile.write( bytes( "<body><p>Error: unable to detect client code in URL.</p></body>", "utf-8" ) )
		self.wfile.write(bytes("</html>", "utf-8"))
		raise KeyboardInterrupt
