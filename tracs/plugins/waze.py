from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from logging import getLogger
from pathlib import Path
from re import match
from re import sub
from typing import Any
from typing import cast
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from click import echo
from dateutil.tz import gettz
from dateutil.tz import UTC
from gpxpy.gpx import GPX
from gpxpy.gpx import GPXTrack
from gpxpy.gpx import GPXTrackPoint
from gpxpy.gpx import GPXTrackSegment

from .gpx import GPX_TYPE
from .gpx import GPXImporter
from .handlers import CSVHandler
from ..activity import Activity
from ..activity_types import ActivityTypes
from ..config import ApplicationContext
from ..handlers import ResourceHandler
from ..protocols import SpecificActivity
from ..registry import importer
from ..registry import Registry
from ..registry import resourcetype
from ..registry import service
from ..resources import Resource
from ..service import Service
from ..utils import as_datetime

log = getLogger( __name__ )

TAKEOUTS_DIRNAME = 'takeouts'
ACTIVITY_FILE = 'account_activity_3.csv'

SERVICE_NAME = 'waze'
DISPLAY_NAME = 'Waze'

WAZE_TYPE = 'text/vnd.waze+txt'
WAZE_TAKEOUT_TYPE = 'text/vnd.waze+csv'
WAZE_ACCOUNT_ACTIVITY_TYPE = 'text/vnd.waze.activity+csv'
WAZE_ACCOUNT_INFO_TYPE = 'text/vnd.waze.info+csv'

DEFAULT_FIELD_SIZE_LIMIT = 131072

@dataclass
class WazePoint:
	str_format = '%y%m%d%H%M%S'

	key: int = field( default=None )
	time: datetime = field( default=None )
	lat: float = field( default=None )
	lon: float = field( default=None )

	def time_as_str( self ) -> str:
		return self.time.strftime( WazePoint.str_format )

	def time_as_int( self ) -> int:
		return int( self.time_as_str() )

@resourcetype( type=WAZE_TYPE, summary=True )
@dataclass
class WazeActivity:

	points: List[WazePoint] = field( default_factory=list )

	def as_activity( self ) -> Activity:
		p0 = cast( WazePoint, self.points[0] )
		return Activity(
			time = p0.time,
			localtime=as_datetime( p0.time, tz=gettz() ),
			type = ActivityTypes.drive,
			uids = [f'{SERVICE_NAME}:{p0.time_as_int()}']
		)

@dataclass
class DriveSummary:

	date: str = field( default=None )
	destination: str = field( default=None )
	source: str = field( default=None )

@dataclass
class Favourites:

	place: str = field( default=None )
	name: str = field( default=None )
	type: str = field( default=None )

@dataclass
class LocationDetails:

	date: str = field( default=None )
	coordinates: str = field( default=None )

@dataclass
class LoginDetails:

	login_time: str = field( default=None )
	logout_time: str = field( default=None )
	total_distance: str = field( default=None )
	device_manufacturer: str = field( default=None )
	device_model: str = field( default=None )
	device_os_version: str = field( default=None )
	waze_version: str = field( default=None )

@dataclass
class CarpoolPreferences:

	free_text: str = field( default=None )
	max_seats_available: str = field( default=None )
	spoken_language: str = field( default=None )
	quiet_ride: str = field( default=None )
	pets_allowed: str = field( default=None )
	smoking_allowed: str = field( default=None )

@dataclass
class UserReport:

	event_date: str = field( default=None )
	type: str = field( default=None )
	pos_x: str = field( default=None )
	pos_y: str = field( default=None )
	subtype: str = field( default=None )

@dataclass
class UserFeedback:

	event_date: str = field( default=None )
	type: str = field( default=None )
	alert_type: str = field( default=None )

@dataclass
class UserCounters:

	traffic_feedback: str = field( default=None )
	gas_prices: str = field( default=None )
	report: str = field( default=None )
	points: str = field( default=None )
	drive: str = field( default=None )

@dataclass
class AccountInfo:

	email: str = field( default=None )
	entry_date: str = field( default=None )
	user_name: str = field( default=None )
	first_name: str = field( default=None )
	last_name: str = field( default=None )
	last_login: str = field( default=None )
	connected_accounts: List[str] = field( default_factory=list )
	user_reports: List[UserReport] = field( default_factory=list )
	user_feedback: List[UserFeedback] = field( default_factory=list )
	user_counters: UserCounters = field( default=UserCounters() )

@dataclass
class WazeTakeout:

	drive_summary: DriveSummary = field( default=DriveSummary() )
	favourites: Favourites = field( default=Favourites() )
	location_details: LocationDetails = field( default=LocationDetails() )
	login_details: LoginDetails = field( default=LoginDetails() )
	carpool_preferences: CarpoolPreferences = field( default=CarpoolPreferences() )
	
	account_info: AccountInfo = field( default=AccountInfo() )

@importer( type=WAZE_ACCOUNT_ACTIVITY_TYPE )
class WazeAccountActivityImporter( CSVHandler ):

	pass

@importer( type=WAZE_ACCOUNT_INFO_TYPE )
class WazeAccountInfoImporter( CSVHandler ):

	class Mode( Enum ):
		NONE = 'NONE'
		GENERAL_INFO = '\ufeffgeneral info'
		CONNECTED_ACCOUNTS = 'connected accounts'
		USER_REPORTS = 'user reports'
		USER_FEEDBACK = 'user feedback'
		USER_COUNTERS = 'user counters'

		@classmethod
		def mode_by_value( cls, line: str ):
			if len( line ) != 1:
				return cls.NONE
			return next( iter( [m for m in cls if m.value == line[0].lower()] ), cls.NONE )

	def __init__( self ) -> None:
		super().__init__( resource_type=WAZE_ACCOUNT_INFO_TYPE, activity_cls=AccountInfo )

	def postprocess_data( self, resource: Resource, **kwargs ) -> None:
		account_info = AccountInfo()
		while resource.raw:
			line = resource.raw.pop( 0 )
			mode = WazeAccountInfoImporter.Mode.mode_by_value( line )

			if mode == WazeAccountInfoImporter.Mode.GENERAL_INFO:
				while line:
					if line := resource.raw.pop( 0 ):
						setattr( account_info, self._snake( line[0] ), line[1] )

			elif mode == WazeAccountInfoImporter.Mode.CONNECTED_ACCOUNTS:
				while line:
					if line := resource.raw.pop( 0 ):
						account_info.connected_accounts.append( line[0] )

			elif mode == WazeAccountInfoImporter.Mode.USER_REPORTS:
				while line:
					if (line := resource.raw.pop( 0 )) and line != ['Event Date', 'Type', 'Pos X', 'Pos Y', 'Subtype']:
						account_info.user_reports.append( UserReport( *line ) )

			elif mode == WazeAccountInfoImporter.Mode.USER_FEEDBACK:
				while line:
					if (line := resource.raw.pop( 0 )) and line != ['Event Date','Type','Alert Type']:
						account_info.user_feedback.append( UserFeedback( *line ) )

			elif mode == WazeAccountInfoImporter.Mode.USER_COUNTERS:
				while line:
					if (line := resource.raw.pop( 0 )) and line != ['Count','Name']:
						setattr( account_info.user_counters, line[1], line[0] )

		resource.raw = account_info

	# noinspection PyMethodMayBeStatic
	def _snake( self, s: str ) -> str:
		return s.lower().replace( ' ', '_' )

@importer( type=WAZE_TYPE )
class WazeImporter( ResourceHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=WAZE_TYPE, activity_cls=WazeActivity )

	def load( self, path: Optional[Path] = None, url: Optional[str] = None, **kwargs ) -> Optional[Resource]:
		if from_str := kwargs.get( 'from_string', False ):
			self.resource = Resource( content=from_str.encode( encoding='UTF-8' ) )
			self.load_data( self.resource )
		else:
			super().load( path, url, **kwargs )

		return self.resource

	def load_data( self, resource: Resource, **kwargs ) -> Any:
		resource.raw = self.read_drive( self.as_str( resource.content ) )

	# noinspection PyMethodMayBeStatic
	def read_drive( self, s: str ) -> List[WazePoint]:
		points: List[WazePoint] = []

		s = s.strip( '[]' )
		for segment in s.split( '};{' ):
			segment = segment.strip( '{}' )
			key, value = segment.split( sep=':', maxsplit=1 )  # todo: what exactly is meant by the key being a number starting with 0?
			key, value = key.strip( '"' ), value.strip( '"' )
			for token in value.split( " => " ):
				# need to match two versions:
				# version 1 (2020): 2020-01-01 12:34:56(50.000000; 10.000000)
				# version 2 (2022): 2022-01-01 12:34:56 GMT(50.000000; 10.000000)
				if m := match( '(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d).*\((\d+\.\d+); (\d+\.\d+)\)', token ):
					timestamp, lat, lon = m.groups()
					points.append( WazePoint( int( key ), datetime.strptime( timestamp, '%Y-%m-%d %H:%M:%S' ).replace( tzinfo=UTC ), float( lat ), float( lon ) ) )
				else:
					raise RuntimeError( f'Error parsing Waze drive while processing token {token}' )

		return points

	def as_activity( self, resource: Resource ) -> Optional[SpecificActivity]:
		return WazeActivity( points=resource.raw )

@importer( type=WAZE_TAKEOUT_TYPE )
class WazeTakeoutImporter( CSVHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=WAZE_TAKEOUT_TYPE )
		self.importer = WazeImporter()

	def load_data( self, resource: Resource, **kwargs ) -> None:
		super().load_data( resource, **kwargs )

		parse_mode = False
		for row in resource.raw:
			if len( row ) == 3 and row[0] == 'Location details (date':
				parse_mode = True

			elif parse_mode and row:
				try:
					r = Resource( raw=self.importer.read_drive( row[0] ), text=row[0], type=WAZE_TAKEOUT_TYPE )
					self.resource.resources.append( r )
				except RuntimeError:
					log.error( 'Error parsing row' )

			elif parse_mode and not row:
				parse_mode = False

@service
class Waze( Service ):

	def __init__( self, **kwargs ):
		super().__init__( **{ **{'name': SERVICE_NAME, 'display_name': DISPLAY_NAME}, **kwargs } )

		self.takeout_importer: WazeTakeoutImporter = cast( WazeTakeoutImporter, Registry.importer_for( WAZE_TAKEOUT_TYPE ) )
		self.takeout_importer.field_size_limit = kwargs.get( 'field_size_limit' ) or DEFAULT_FIELD_SIZE_LIMIT
		log.debug( f'using {self.takeout_importer.field_size_limit} as field size limit for CSV parser in Waze service' )

		self.importer: WazeImporter = cast( WazeImporter, Registry.importer_for( WAZE_TYPE ) )
		self.gpx_importer: GPXImporter = cast( GPXImporter, Registry.importer_for( GPX_TYPE ) )

		self._logged_in = True

	def path_for_id( self, local_id: int, base_path: Optional[Path] ) -> Path:
		_id = str( local_id )
		path = Path( _id[0:2], _id[2:4], _id[4:6], _id )
		if base_path:
			path = Path( base_path, path )
		return path

	def path_for( self, activity: Activity = None, resource: Resource = None, ext: Optional[str] = None ) -> Optional[Path]:
		"""
		Returns the path for an activity.

		:param activity: activity for which the path shall be calculated
		:param resource: resource
		:param ext: file extension
		:return: path for activity
		"""
		_id = str( activity.raw_id ) if activity else str( resource.raw_id )
		path = Path( self.base_path, _id[0:2], _id[2:4], _id[4:6], _id )
		if resource:
			path = Path( path, resource.path )
		elif ext:
			path = Path( path, f'{id}.{ext}' )
		return path

	def url_for_id( self, local_id: Union[int, str] ) -> Optional[str]:
		return None

	def url_for_resource_type( self, local_id: Union[int, str], type: str ) -> Optional[str]:
		return None

	def login( self ) -> bool:
		return self._logged_in

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		takeouts_dir = self.ctx.takeouts_dir_for( self.name )
		log.debug( f"fetching Waze activities from {takeouts_dir}" )

		takeout_files = sorted( takeouts_dir.rglob( ACTIVITY_FILE ) )
		# self.ctx.start( f'fetching activity summaries from {self.display_name}', len( takeout_files ) )
		# last_fetch = self.state_value( KEY_LAST_FETCH )

		summaries = []

		for file in takeout_files:
			self.ctx.advance( f'{file}' )
			log.debug( f'fetching activities from Waze takeout in {file}' )

			rel_path = file.relative_to( takeouts_dir ).parent
			if (_takeouts := self.state_value( 'takeouts' )) and rel_path.name in _takeouts:
				continue

			# don't look at mtime, not convenient during development
			# mtime = datetime.fromtimestamp( getmtime( file ), UTC )
			# if last_fetch and datetime.fromisoformat( last_fetch ) >= mtime and not force:
			#	log.debug( f"skipping Waze takeout in {file} as it is older than the last_fetch timestamp, consider --force to ignore timestamps"  )
			#	continue

			takeout_resource = self.takeout_importer.load( path=file )
			for resource in takeout_resource.resources:
				local_id = cast( WazePoint, resource.raw[0] ).time_as_int()
				resource.path = f'{local_id}.txt'
				resource.status = 200
				# resource.source = file.as_uri() # don't save the source right now
				resource.summary = True
				resource.type = WAZE_TYPE
				resource.uid = f'{self.name}:{local_id}'

				summaries.append( resource )

		# self.ctx.complete( 'done' )

		log.debug( f'fetched {len( summaries )} Waze activities' )

		return summaries

	def download( self, summary: Resource, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		if not summary.get_child( GPX_TYPE ) or force:
			try:
				gpx_resource = Resource( type=GPX_TYPE, path=f'{summary.local_id}.gpx', uid=summary.uid )
				self.download_resource( gpx_resource, summary=summary )
				return [gpx_resource]
			except RuntimeError:
				log.error( f'error fetching resource from {summary.uid}', exc_info=True )
		return []

	def download_resource( self, resource: Resource, **kwargs ) -> Tuple[Any, int]:
		if (summary := kwargs.get( 'summary' )) and summary.raw:
			resource.raw, resource.content = to_gpx( summary.raw )
			resource.status = 200
		else:
			local_path = Path( self.path_for( resource=resource ).parent, f'{resource.local_id}.txt' )
			with open( local_path, mode='r', encoding='UTF-8' ) as p:
				content = p.read()
				drive = self.importer.read_drive( content )
				gpx = to_gpx( drive )
				return gpx, 200  # return always 200

	# def postdownload( self, ctx: ApplicationContext ) -> None:
	# 	summary = import_session.last_summary
	# 	if activity := import_session.fetched_activities.get( (summary.uid, summary.path) ):
	# 		gpx_activity = self.gpx_importer.as_activity( import_session.last_download[0] )
	# 		new_activity = Activity().init_from( activity ).init_from( other=gpx_activity )
	# 		new_activity.uids.append( activity.uid )
	# 		ctx.db.upsert_activity( new_activity, uid=activity.uid )

	# nothing to do for now ...
	def setup( self, ctx: ApplicationContext ):
		echo( 'Skipping setup for Waze ... nothing to configure at the moment' )

	# noinspection PyMethodMayBeStatic
	def setup_complete( self ) -> bool:
		return True

# helper functions

def to_gpx( points: List[WazePoint] ) -> Tuple[GPX, bytes]:
	trackpoints = [GPXTrackPoint( time=p.time, latitude=p.lat, longitude=p.lon ) for p in points]
	segment = GPXTrackSegment( points=trackpoints )
	track = GPXTrack()
	track.segments.append( segment )
	gpx = GPX()
	gpx.tracks.append( track )
	return gpx, bytes( gpx.to_xml(), 'UTF-8' )
