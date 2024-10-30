from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import zip_longest
from logging import getLogger
from pathlib import Path
from re import compile, match
from sys import exit as sysexit
from time import time
from typing import Any, Dict, List, Optional, Tuple, Union
from webbrowser import open as open_url

from dateutil.parser import parse as dtparse
from dateutil.tz import tzlocal, UTC
from fs.base import FS
from fs.path import dirname
from lxml.etree import tostring
from requests import get as rqget
from rich.prompt import Prompt
from stravalib.client import Client
from stravalib.model import DetailedActivity as StravaActivity

from tracs.activity import Activities, Activity
from tracs.activity_types import ActivityTypes
from tracs.config import ApplicationContext, APPNAME
from tracs.pluginmgr import importer, resourcetype, service, setup
from tracs.plugins.gpx import GPX_TYPE
from tracs.plugins.image import JPEG_TYPE
from tracs.plugins.json import JSONHandler
from tracs.plugins.stravaconstants import BASE_URL, TYPES
from tracs.plugins.tcx import TCX_TYPE
from tracs.resources import Resource, ResourceType
from tracs.service import Service
from tracs.streams import Point, Stream

log = getLogger( __name__ )

SERVICE_NAME = 'strava'
DISPLAY_NAME = 'Strava'

STRAVA_TYPE = 'application/vnd.strava+json'

OAUTH_REDIRECT_URL = 'http://localhost:40004'
SCOPE = 'activity:read_all'

FETCH_PAGE_SIZE = 30 #
PHOTO_SIZE = 2800

TIMEZONE_FULL_REGEX = compile( '^(\(.+\)) (.+)$' ) # not used at the moment
TIMEZONE_REGEX = compile( '\(\w+\+\d\d:\d\d\) ' )

# register Strava Activity type
# register CSV type
@resourcetype
def strava_resource_type() -> ResourceType:
	return ResourceType( type=STRAVA_TYPE, summary=True )

@importer( type=STRAVA_TYPE )
class StravaHandler( JSONHandler ):

	TYPE: str = STRAVA_TYPE
	ACTIVITY_CLS = StravaActivity

	def load_data( self, raw: Any, **kwargs ):
		return StravaActivity.parse_obj( raw )

	def save_data( self, data: Any, **kwargs ) -> Any:
		return StravaActivity.dict( data )

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		da: StravaActivity = resource.data
		tz_str = str( da.timezone ) if da.timezone else str( tzlocal() )

		# noinspection Py
		activity = Activity(
			name = da.name,
			type = TYPES.get( da.type.root, ActivityTypes.unknown ),
			starttime= da.start_date,
			starttime_local= da.start_date_local.astimezone( da.timezone.timezone() ),
			timezone = tz_str,
			distance = float( da.distance or 0.0 ),
			speed = float( da.average_speed or 0.0 ),
			speed_max = float( da.max_speed or 0.0 ),
			ascent = float( da.total_elevation_gain or 0.0 ),
			descent = float( da.total_elevation_gain or 0.0 ),
			elevation_max = float( da.elev_high or 0.0 ),
			elevation_min = float( da.elev_low or 0.0 ),
			duration = da.elapsed_time.timedelta(),
			duration_moving = da.moving_time.timedelta(),
			heartrate = int( da.average_heartrate or 0 ),
			heartrate_max = int( da.max_heartrate or 0 ),
			location_country = da.location_country,
			uid = f'{SERVICE_NAME}:{da.id}',
		)

		for f in Activity.fields():
			if getattr( activity, f.name ) in [ 0, 0.0 ]:
				setattr( activity, f.name, None )

		return activity

@service
class Strava( Service ):

	def __init__( self, **kwargs ):
		super().__init__( **{ **{'name': SERVICE_NAME, 'display_name': DISPLAY_NAME, 'base_url': BASE_URL}, **kwargs } )

		self._client = Client()
		self._session = None
		self._oauth_session = None

		self.importer: StravaHandler = StravaHandler()
		self.json_handler: JSONHandler = JSONHandler()

	@property
	def activities_url( self ) -> str:
		return f'{self.base_url}/activities'

	def url_events_year( self, year, page: int ) -> str:
		after = int( datetime( year, 1, 1, tzinfo=UTC ).timestamp() )
		before = int( datetime( year + 1, 1, 1, tzinfo=UTC ).timestamp() )
		per_page = FETCH_PAGE_SIZE # we might make this configurable later ...
		return f'{self.base_url}/api/v3/athlete/activities?before={before}&after={after}&page={page}&per_page={per_page}'

	def all_events_url( self, page: int ) -> str:
		after = int( datetime( 1970, 1, 1, tzinfo=UTC ).timestamp() )
		before = int( datetime( datetime.utcnow().year + 1, 1, 1, tzinfo=UTC ).timestamp() )
		per_page = FETCH_PAGE_SIZE  # we might make this configurable later ...
		return f'{self.base_url}/api/v3/athlete/activities?before={before}&after={after}&page={page}&per_page={per_page}'

	def url_for_id( self, local_id: Union[int, str] ) -> Optional[str]:
		return f'{self.activities_url}/{local_id}'

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

	# service methods

	def supports_remote_import( self ) -> bool:
		return True

	def login( self ):
		# check if access/refresh tokens are available
		if not self.state_value( 'access_token' ) and not self.state_value( 'refresh_token' ):
			log.error( f"application setup not complete for {SERVICE_NAME}, consider running {APPNAME} setup --strava" )
			sysexit( -1 )

		self._client = Client( access_token=self.state_value( 'access_token' ) )

		if time() > self.state_value( 'expires_at' ):
			log.debug( f"access token has expired, attempting to fetch new one" )
			client_id = self.cfg_value( 'client_id' )
			client_secret = self.cfg_value( 'client_secret' )
			refresh_token = self.state_value( 'refresh_token' )
			refresh_response = self._client.refresh_access_token( client_id=client_id, client_secret=client_secret, refresh_token=refresh_token )

			self.set_state_value( 'access_token', refresh_response.get( 'access_token' ) )
			self.set_state_value( 'refresh_token', refresh_response.get( 'refresh_token' ) )
			self.set_state_value( 'expires_at', refresh_response.get( 'expires_at' ) )

		# todo: how to detect unsuccessful login?
		return True

	def import_from_remote( self, dst_fs: FS, **kwargs ) -> Activities:
		if not self.login():
			return Activities()

		after = kwargs.get( 'range_from' )
		before = kwargs.get( 'range_to' )
		first_year = self.ctx.config['import'].first_year

		if after is None or before is None:
			after, before = datetime( first_year, 1, 1 ), datetime.now( UTC ) + timedelta( days = 1 )

		activities = Activities()

		# sa = SummaryActivity, da = DetailedActivity
		for sa in self._client.get_activities( after=after, before=before ):
			self.ctx.advance( f'activity {sa.id}' )

			uid = f'{self.name}:{sa.id}'
			path = f'{self.path_for_id( sa.id, self.name )}/{sa.id}.json'

			if self.ctx.force or not self.db.contains_resource( uid, path ):
				da = self._client.get_activity( sa.id, include_all_efforts=True )  # get detailed data for activity

				# summary
				summary = Resource(
					content=da.model_dump_json( exclude_unset=True, exclude_defaults=True, exclude_none=True, indent=2 ).encode( 'UTF-8' ),
					raw=da.model_dump( exclude_unset=True, exclude_defaults=True, exclude_none=True ),
					data=da,
					uid=uid,
					path=path,
					type=STRAVA_TYPE,
					source=self.url_for_id( da.id ),
				)

				# streams

				# available streams:
				# time, latlng, distance, altitude, velocity_smooth, heartrate, cadence, watts, temp, moving, grade_smooth
				# gpx contains lat/lon, elevation, time + time in metadata
				# tcx contains TotalTimeSeconds, DistanceMeters, MaximumSpeed, Calories
				# track contains Time, LatitudeDegrees, LongitudeDegrees, AltitudeMeters, DistanceMeters, SensorState
				streams = self._client.get_activity_streams( da.id, types=[ 'time', 'latlng', 'distance', 'altitude', 'velocity_smooth', 'heartrate' ] )
				stream = to_stream( streams, summary.data.start_date )

				# TCX

				tcx = stream.as_tcx(
					average_heart_rate_bpm = summary.raw.get( 'average_heartrate' ),
					calories = round( summary.raw.get( 'calories' ) ),
					distance_meters = summary.raw.get( 'distance' ),
					id = f'{summary.raw.get( "start_date_local" )}Z',
					intensity = 'Active', # todo: don't know where to get this from
					maximum_heart_rate_bpm = summary.raw.get( 'max_heartrate' ),
					maximum_speed = summary.raw.get( 'max_speed' ),
					start_date = dtparse( sd ) if type( sd := summary.raw.get( 'start_date' ) ) is str else sd,
					# trigger_method = 'Distance', # todo: this is not correct
					total_time_seconds = round( summary.raw.get( 'elapsed_time' ) ),
				)
				tcx_recording = Resource(
					uid=summary.uid,
					path=f'{summary.path[0:-4]}tcx',
					text=tostring( tcx.as_xml(), pretty_print=True ).decode( 'UTF-8' ),
					type=TCX_TYPE,
				)

				# GPX

				gpx_recording = None
				if any( p.lat for p in stream.points ):
					gpx = stream.as_gpx(
						track_name = summary.raw.get( 'name' ),
						# track_type = '1' # todo: don't know what GPX type means, strava uses integer numbers
					)
					gpx_recording = Resource(
						uid=summary.uid,
						path=f'{summary.path[0:-4]}gpx',
						type=GPX_TYPE,
						text=gpx.to_xml( prettyprint=True )
					)

				# Photos

				photos = []
				if summary.raw.get( 'photos' ).get( 'count' ) > 0:
					for photo, index in zip( self._client.get_activity_photos( summary.raw.get( 'id' ), size=PHOTO_SIZE ), range( 1, 100 ) ):
						photo_url = photo.urls.get( str( PHOTO_SIZE ) )
						if ( response := rqget( photo_url ) ) and response.status_code == 200:
							photos.append(
								Resource(
									content=response.content,
									path=f'{summary.path[0:-4]}{index}.jpg',
									type=JPEG_TYPE,
									uid=summary.uid,
								)
							)

				# write resources
				dst_fs.makedirs( dirname( path ), recreate=True )
				dst_fs.writebytes( summary.path, contents=summary.content )
				dst_fs.writebytes( tcx_recording.path, contents=tcx_recording.content )
				if gpx_recording:
					dst_fs.writebytes( gpx_recording.path, contents=gpx_recording.content )
				for p in photos:
					dst_fs.writebytes( p.path, contents=p.content )
				log.debug( f'wrote summary to {dst_fs}/{summary.path}' )

				# create activity and unload resources
				activity = self.importer.load_as_activity( resource=summary )
				activity.resources.append( tcx_recording )
				if gpx_recording:
					activity.resources.append( gpx_recording )
				activity.resources.extend( photos )

				summary.unload()
				tcx_recording.unload()
				if gpx_recording:
					gpx_recording.unload()
				for p in photos:
					p.unload()
				activities.append( activity )

		return activities

	@property
	def logged_in( self ) -> bool:
		return True if self._session and self._oauth_session else False

# setup

INTRO_TEXT = f'GPX and TCX files from Strava will be downloaded via Strava\'s Web API, that\'s why your credentials are needed.'
# https://developers.strava.com/docs/authentication/
CLIENT_ID_TEXT = 'Checking for new activities and downloading photos works by using Strava\'s REST API. To be able ' \
                 'to use this API you need to enter your Client ID and your Client Secret. In order to retrieve both, ' \
                 'you need to create your own Strava application. Head to https://www.strava.com/settings/api ' \
                 'and enter all necessary details. Once you created your application, the ID and the secret ' \
                 'will be displayed.'

# return { 'username': user, 'password': password }, {}

@setup
def setup( ctx: ApplicationContext, config: Dict, state: Dict ) -> Tuple[Dict, Dict]:
	ctx.console.print( INTRO_TEXT, width=120 )

	client = Client()

	ctx.console.print()
	ctx.console.print( CLIENT_ID_TEXT, width=120 )
	ctx.console.print()

	client_id = Prompt.ask( 'Enter your Client ID', console=ctx.console, default=config.get( 'client_id', '' ) )
	ctx.console.print()
	client_secret = Prompt.ask( 'Enter your Client Secret', console=ctx.console, default=config.get( 'client_secret', '' ) )
	ctx.console.print()

	authorize_url = client.authorization_url( client_id=client_id, redirect_uri=OAUTH_REDIRECT_URL, scope=SCOPE )

	client_code_text = f'For the next step we need to obtain the Client Code. The client code can be obtained by visiting this ' \
	                   f'URL: {authorize_url} After authorizing {APPNAME} you will be redirected to {OAUTH_REDIRECT_URL} and the ' \
	                   f'code is part of the URL displayed in your browser. Have a look at the displayed ' \
	                   f'URL: {OAUTH_REDIRECT_URL}?code=<CLIENT_CODE_IS_DISPLAYED_HERE>&scope={SCOPE}'

	ctx.console.print()
	ctx.console.print( client_code_text )
	ctx.console.print()
	client_code = Prompt.ask( f'Enter your Client Code or press enter to open the link in your browser and let {APPNAME} autodetect the code.', console=ctx.console )
	ctx.console.print()

	if not client_code:
		open_url( authorize_url )
		webServer = HTTPServer( ('localhost', 40004), StravaSetupServer )

		try:
			webServer.serve_forever()
		except KeyboardInterrupt:
			pass

		client_code = StravaSetupServer.client_code
		webServer.server_close()

	try:
		token_response = client.exchange_code_for_token( client_id=client_id, client_secret=client_secret, code=client_code )
		access_token = token_response.get( 'access_token' )
		refresh_token = token_response.get( 'refresh_token' )
		expires_at = token_response.get( 'expires_at' )
		log.debug( f"fetched access and refresh token for athlete {client.get_athlete().id}, expiring at {expires_at}" )

		return { 'client_code': client_code, 'client_id': client_id, 'client_secret': client_secret },\
			{ **state, 'access_token': access_token, 'refresh_token': refresh_token, 'expires_at': expires_at }

	except RuntimeError as rte:
		ctx.console.print( f'Error: authorization not granted.' )
		ctx.console.print( rte )
		return {}, {}

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
			self.wfile.write(bytes("<body><p>Client code successfully detected, you can close this window.</p></body>", "utf-8"))
		else:
			self.wfile.write( bytes( "<body><p>Error: unable to detect client code in URL.</p></body>", "utf-8" ) )
		self.wfile.write(bytes("</html>", "utf-8"))
		raise KeyboardInterrupt

# helper

class EmptyStream:

	@property
	def data( self ) -> List:
		return []

EMPTY = EmptyStream()

def to_stream( streams: Dict, start_date: datetime ) -> Stream:
	stream_iterator = zip_longest(
		streams.get( 'time', EMPTY ).data,
		streams.get( 'latlng', EMPTY ).data,
		streams.get( 'distance', EMPTY ).data,
		streams.get( 'altitude', EMPTY ).data,
		streams.get( 'velocity_smooth', EMPTY ).data,
		streams.get( 'heartrate', EMPTY ).data,
		fillvalue=None
	)
	points = [ Point( distance=d, alt=a, speed=vs, hr=hr, start=start_date, seconds=t, latlng=ll ) for t, ll, d, a, vs, hr in stream_iterator ]
	return Stream( points=points )
