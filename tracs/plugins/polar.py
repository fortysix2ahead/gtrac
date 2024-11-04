from datetime import datetime, time, timedelta
from itertools import chain, zip_longest
from logging import getLogger
from math import remainder
from pathlib import Path
from re import compile, match
from sys import exit as sysexit
from time import time as current_time
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
from zipfile import BadZipFile

from attrs import define, field
from babel.dates import get_timezone
from bs4 import BeautifulSoup
from click import echo
from datetimerange import DateTimeRange
from dateutil.parser import parse
from dateutil.tz import tzlocal, UTC
from fs import open_fs
from fs.base import FS
from fs.errors import CreateFailed
from fs.path import dirname
from fs.zipfs import ReadZipFS
from helpers import gpx_resource
from lxml.etree import tostring
from more_itertools import first, first_true
from regex import compile
from requests_cache import CachedSession
from rich.prompt import Prompt
from streams import Point, Stream

from tracs.activity import Activities, Activity, ActivityPart
from tracs.activity_types import ActivityTypes, ActivityTypes as Types
from tracs.aio import load_resource
from tracs.config import ApplicationContext, APPNAME
from tracs.pluginmgr import importer, resourcetype, service, setup
from tracs.plugins.gpx import GPX_TYPE, GPXImporter
from tracs.plugins.json import DataclassFactoryHandler, JSONHandler
from tracs.plugins.polar_takeout import PolarFlowTakeoutImporter
from tracs.plugins.tcx import TCX_TYPE
from tracs.plugins.xml import XMLHandler
from tracs.resources import Resource
from tracs.service import Service, path_for_id
from tracs.utils import seconds_to_time, to_isotime
from tracs.uid import UID

log = getLogger( __name__ )

# general purpose fields/headers/type definitions

SERVICE_NAME = 'polar'
DISPLAY_NAME = 'Polar Flow'

POLAR_CSV_TYPE = 'text/vnd.polar+csv'
POLAR_HRV_TYPE = 'text/vnd.polar.hrv+csv'
POLAR_FLOW_TYPE = 'application/vnd.polar+json'
POLAR_FITNESS_TEST_TYPE = 'application/vnd.polar.fitness+json'
POLAR_ORTHOSTATIC_TEST_TYPE = 'application/vnd.polar.orthostatic+json'
POLAR_RRRECORDING_TYPE = 'application/vnd.polar.rrrecording+json'
POLAR_SESSION_TYPE = 'application/vnd.polar.session+json'
POLAR_EXERCISE_DATA_TYPE = 'application/vnd.polar.ped+xml'
POLAR_ZIP_GPX_TYPE = 'application/vnd.polar.gpx+zip'
POLAR_ZIP_TCX_TYPE = 'application/vnd.polar.tcx+zip'

ACCOUNT_DATA_GLOB = 'account-data-*.json'
ACCOUNT_PROFILE_GLOB = 'account-profile-*.json'
TRAINING_SESSION_GLOB = 'training-session-*.json'

TRAINING_SESSION_REGEX = compile( r'^.*training-session-(\d{4}-\d{2}-\d{2})-(\d+)(-([a-f0-9-]+))*\.json$' )

PED_NS = 'http://www.polarpersonaltrainer.com'

# polar icon ids for identifying multipart activities: there does not seem to be any other way to identify those
ICON_ID_TRIATHLON = '003304795bc33d808ee8e6ab8bf45d1f-2015-10-20_13_45_17'  # triathlon
ICON_ID_MULTISPORT = '20951a7d8b02def8265f5231f57f4ed9-2015-10-20_13_45_40'  # multisport

BASE_URL = 'https://flow.polar.com'

HEADERS_TEMPLATE = {
	'Accept-Encoding': 'gzip, deflate, br',
	'Accept-Language': 'en-US,en;q=0.5',
	'Connection': 'keep-alive',
	'DNT': '1',
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
}

HEADERS_LOGIN = { **HEADERS_TEMPLATE, **{
	'Accept': '*/*',
	'Cache-Control': 'no-cache',
	'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
	'Host': 'flow.polar.com',
	'Origin': 'https://flow.polar.com',
	'Pragma': 'no-cache',
	'Referer': 'https://flow.polar.com/',
	'TE': 'Trailers',
	# 'X-Requested-With': 'XMLHttpRequest'
} }

HEADERS_API = { **HEADERS_TEMPLATE, **{
	'Accept': 'application/json',
	# 'Cache-Control': 'no-cache',
} }

HEADERS_DOWNLOAD = { **HEADERS_TEMPLATE, **{
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
	# 'Cache-Control': 'no-cache',
	'Host': 'flow.polar.com',
	# 'Referer': 'https://flow.polar.com/training/analysis/{polar_id}',
	'TE': 'Trailers',
	# 'X-Requested-With': 'XMLHttpRequest'
} }

# all types: https://www.polar.com/accesslink-api/#detailed-sport-info-values-in-exercise-entity
# this maps the last part of the icon URL to Polar sports types, there's no other way to find the actual type
# example: iconUrl = "https://platform.cdn.polar.com/ecosystem/sport/icon/808d0882e97375e68844ec6c5417ea33-2015-10-20_13_46_22
TYPES = {
	'003304795bc33d808ee8e6ab8bf45d1f-2015-10-20_13_45_17': Types.triathlon,
	'20951a7d8b02def8265f5231f57f4ed9-2015-10-20_13_45_40': Types.multisport,
	'22f701a2c43d7c5678140b0a3e52ddaa-2015-10-20_13_46_02': Types.rollski_classic,
	'2524f40bcd8372f0912cb213c1fc9a29-2015-10-20_13_45_29': Types.bike_road,
	'3c1103ccbeee33fa663a1dc8e0fd8a6d-2015-10-20_13_45_48': Types.xcski_classic,
	'3e8556e6cf6ed3f01e5f8af133117416-2015-10-20_13_46_00': Types.rollski_free,
	'40894732d0b606b3fd9c9c34471df222-2015-10-20_13_46_28': Types.swim_indoor,
	'49b881c0a9aec1fce68fab11f8f1b01d-2016-02-03_06_06_42': Types.gymnastics,
	'4c54b3b02bd2d8b9b3f60931776a3497-2015-10-20_13_46_07': Types.unknown,
	'4ddd474b10302e72fb53bbd69028e15b-2015-10-20_13_46_17': Types.bike_mountain,
	'561a80f6d7eef7cc328aa07fe992af8e-2015-10-20_13_46_03': Types.bike,
	'5cdfcd252814f732414d977484cef4ea-2015-10-20_13_46_11': Types.swim_outdoor,
	'808d0882e97375e68844ec6c5417ea33-2015-10-20_13_46_22': Types.run,
	'9e3fc7036226634543f971acd1a68e60-2015-11-25_10_37_05': Types.ergo,
	'a2afcae540681c227a48410d97277e2e-2015-10-20_13_45_18': Types.unknown,
	'a2e8c7a794dadb60ecbfb21239f5b981-2016-02-03_06_06_32': Types.unknown,
	'd1ce94078aec226be28f6c602e6803e1-2015-10-20_13_45_19': Types.gym,
	'e25370188b9c9b611dcafb6f0028faeb-2015-10-20_13_45_32': Types.hiking,
	'f0c9643f1cef947e5621b0b46ab06783-2015-10-20_13_46_12': Types.xcski_free,
	'f4197b0c1a4d65962b9e45226c77d4d5-2015-10-20_13_45_26': Types.swim,
}

@define
class ResourcePartlist:

	index: int = field( default=0 )
	range: DateTimeRange = field( default=None )
	resources: List[Resource] = field( factory=list )

	def start( self ) -> datetime:
		return self.range.start_datetime

	def end( self ) -> datetime:
		return self.range.end_datetime

@resourcetype( type=POLAR_FLOW_TYPE, summary=True )
@define
class PolarFlowExercise:

	allDay: bool = field( default=False )
	backgroundColor: Optional[str] = field( default=None )
	borderColor: Optional[str] = field( default=None )
	calories: Optional[int] = field( default=None )
	className: Optional[str] = field( default=None )
	datetime: str = field( default=None ) # 2011-04-28T17:48:10.000Z
	distance: Optional[float] = field( default=None )
	duration: int = field( default=None )
	end: Optional[int] = field( default=None )
	eventType: str = field( default=None )
	hasTrainingTarget: Optional[bool] = field( default=False )
	iconUrl: Optional[str] = field( default=None )
	index: Optional[int] = field( default=None )
	isTest: Optional[bool] = field( default=False )
	listItemId: int = field( default=None )
	start: Optional[int] = field( default=None )
	textColor: Optional[str] = field( default=None )
	timestamp: int = field( default=None )
	title: str = field( default=None )
	type: str = field( default=None )
	url: str = field( default=None )

	@property
	def is_multipart( self ):
		return _is_multipart_id( self.iconUrl )

	@property
	def local_id( self ) -> int:
		if self.eventType == 'exercise' or self.eventType == 'fitnessData':
			return self.listItemId
		elif self.eventType == 'orthostaticTest':
			return int( match('.*id=(\d+).*', self.url )[1] )
		elif self.eventType == 'rrTest':
			return int( match('.*/rr/(\d+)', self.url )[1])
		return 0

	@property
	def uid( self ):
		return f'{SERVICE_NAME}:{self.local_id}'

	def get_type( self ) -> ActivityTypes:
		return TYPES.get( self.iconUrl.rsplit( '/', 1 )[1], Types.unknown ) if self.iconUrl else Types.unknown

@resourcetype( type=POLAR_FITNESS_TEST_TYPE )
@define
class PolarFitnessTest:

	allDay: bool = field( default=False )
	backgroundColor: str = field( default=None )
	borderColor: str = field( default=None )
	className: str = field( default=None )
	datetime: str = field( default=None ) # 2011-04-28T17:48:10.000Z
	eventType: str = field( default=None )
	index: int = field( default=None )
	listItemId: int = field( default=None )
	start: str = field( default=None )
	textColor: str = field( default=None )
	timestamp: int = field( default=None )
	title: str = field( default=None )
	type: str = field( default=None )
	url: str = field( default=None )

@resourcetype( type=POLAR_ORTHOSTATIC_TEST_TYPE )
@define
class PolarOrthostaticTest:

	_RX_URL = compile( r'/progress/tests\?type=orthostatic_test&id=(\d+)' )

	datetime: str = field( default=None ) # 2011-04-28T17:48:10.000Z
	eventType: str = field( default=None )
	result: str = field( default=None )
	title: str = field( default=None )
	type: str = field( default=None )
	url: str = field( default=None )

	@property
	def local_id( self ) -> int:
		return int( self.__class__._RX_URL.fullmatch( self.url ).groups()[0] )

@resourcetype( type=POLAR_RRRECORDING_TYPE )
@define
class PolarRRRecording:

	_RX_URL = compile( r'/training/test/rr/(\d+)' )

	datetime: str = field( default=None ) # 2011-04-28T17:48:10.000Z
	eventType: str = field( default=None )
	result: str = field( default=None )
	title: str = field( default=None )
	type: str = field( default=None )
	url: str = field( default=None )

	@property
	def local_id( self ) -> int:
		return int( self.__class__._RX_URL.fullmatch( self.url ).groups()[0] )

@resourcetype( type=POLAR_CSV_TYPE )
@define
class PolarFlowExerciseCsv:

	pass

@resourcetype( type=POLAR_HRV_TYPE )
@define
class PolarFlowExerciseHrv:

	pass

@resourcetype( type=POLAR_SESSION_TYPE )
@define
class PolarTrainingSession:

	pass

# todo: this needs an update, but has low priority
@resourcetype( type=POLAR_EXERCISE_DATA_TYPE )
class PolarExerciseDataActivity( Activity ):

	def __raw_init__( self, raw: Any ) -> None:
		self.classifier = 'polar'
		self.time = datetime.strptime( self.raw.get( 'time' ), '%Y-%m-%d %H:%M:%S.%f' ).astimezone( UTC )  # 2016-09-15 16:50:27.0
		self.raw_id = int( self.time.strftime( '%y%m%d%H%M%S' ) )
		self.uid = f'{self.classifier}:{self.raw_id}'

@importer
class PolarFlowImporter( DataclassFactoryHandler ):

	TYPE: str = POLAR_FLOW_TYPE
	ACTIVITY_CLS = PolarFlowExercise

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		activity: PolarFlowExercise = resource.data
		return Activity(
			uid = f'{SERVICE_NAME}:{activity.local_id}',
			name = activity.title,
			type = activity.get_type(),
			starttime= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ).astimezone( UTC ),
			starttime_local= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ),
			distance = activity.distance,
			duration = timedelta( seconds = activity.duration / 1000 ) if activity.duration else None,
			calories = activity.calories,
		)

@importer
class PolarFitnessTestImporter( DataclassFactoryHandler ):

	TYPE: str = POLAR_FITNESS_TEST_TYPE
	ACTIVITY_CLS = PolarFitnessTest

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		activity: PolarFitnessTest = resource.data
		return Activity(
			uid = f'{SERVICE_NAME}:{activity.listItemId}',
			name = activity.title,
			type = ActivityTypes.test,
			starttime= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ).astimezone( UTC ),
			starttime_local= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ),
		)

@importer
class PolarOrthostaticTestImporter( DataclassFactoryHandler ):

	TYPE: str = POLAR_ORTHOSTATIC_TEST_TYPE
	ACTIVITY_CLS = PolarOrthostaticTest

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		activity: PolarOrthostaticTest = resource.data
		return Activity(
			uid = f'{SERVICE_NAME}:{activity.local_id}',
			name = activity.title,
			type = ActivityTypes.test,
			starttime= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ).astimezone( UTC ),
			starttime_local= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ),
		)

@importer
class PolarRRRecordingImporter( DataclassFactoryHandler ):

	TYPE: str = POLAR_RRRECORDING_TYPE
	ACTIVITY_CLS = PolarRRRecording

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		activity: PolarRRRecording = resource.data
		return Activity(
			uid = f'{SERVICE_NAME}:{activity.local_id}',
			name = activity.title,
			type = ActivityTypes.test,
			starttime= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ).astimezone( UTC ),
			starttime_local= parse( activity.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ),
		)

@importer
class PolarTrainingSessionImporter( JSONHandler ):

	TYPE: str = POLAR_SESSION_TYPE
	ACTIVITY_CLS = PolarTrainingSession
	
	def __init__( self ):
		super().__init__()
		self.remainders: Optional[List[Activity]] = None
	
	def as_activity( self, resource: Resource ) -> Activity:
		for exc, act in zip( el := resource.data.get( 'exercises', [] ), activities := [Activity() for e in el] ):

			act.ascent = resource.float( 'ascent', parent=exc )
			act.cadence = resource.float( 'cadence', 'avg', parent=exc )
			act.cadence_max = resource.float( 'cadence', 'max', parent=exc )
			act.calories = resource.int( 'kiloCalories', parent=exc )
			act.descent = resource.float( 'descent', parent=exc )
			act.distance = resource.float( 'distance', parent=exc )
			act.duration = resource.td( 'duration', parent=exc )
			act.elevation = resource.float( 'altitude', 'avg', parent=exc )
			act.elevation_max = resource.float( 'altitude', 'max', parent=exc )
			act.elevation_min = resource.float( 'altitude', 'min', parent=exc )
			act.heartrate = resource.int( 'heartRate', 'avg', parent=exc )
			act.heartrate_max = resource.int( 'heartRate', 'max', parent=exc )
			act.heartrate_min = resource.int( 'heartRate', 'min', parent=exc )
			act.location_latitude_start = resource.float( 'latitude', parent=exc )
			act.location_longitude_start = resource.float( 'longitude', parent=exc )
			act.power = resource.float( 'power', 'avg', parent=exc )
			act.power_max = resource.float( 'power', 'max', parent=exc )
			act.speed = resource.float( 'speed', 'avg', parent=exc )
			act.speed_max = resource.float( 'speed', 'max', parent=exc )
			act.starttime = resource.utc( 'startTime', parent=exc )
			act.endtime = resource.utc( 'stopTime', parent=exc )

			# todo: actually this not always correct - when an activity took place in a different timezone than the home zone
			act.timezone = get_timezone().zone
			act.starttime_local= act.starttime.astimezone( tzlocal() )
			act.endtime_local= act.endtime.astimezone( tzlocal() )

			act.resources.append( Resource(
				content=resource.content,
				type=POLAR_SESSION_TYPE,
			) )

			# create streams, todo: make this part more resilient, at the moment it's not clear what data can exist or be missing

			if samples := exc.get( 'samples' ):
				name, values = first( samples.items() )
				points = [ Point() for p in range( len( values ) ) ]
				for pnt, fst, alt, dst, hr, rr, spd in zip_longest(
					points,
					samples.get( name, [] ),
					samples.get( 'altitude', [] ),
					# samples.get( 'cadence', [] ),
					samples.get( 'distance', [] ),
					samples.get( 'heartRate', [] ),
					# samples.get( 'leftPedalCrankBasedPower' ),
					samples.get( 'recordedRoute', [] ),
					samples.get( 'speed', [] ),
					# samples.get( 'strideLength' ),
					# samples.get( 'temperature' ),
					fillvalue={}
				):
					pnt.time = to_isotime( fst.get( 'dateTime' ) ).astimezone( UTC )
					pnt.alt = alt.get( 'value', None )
					pnt.distance = dst.get( 'value', None )
					pnt.hr = hr.get( 'value', None )
					pnt.lat = rr.get( 'latitude', None )
					pnt.lon = rr.get( 'longitude', None )
					pnt.alt = rr.get( 'altitude', None )
					pnt.speed = spd.get( 'value', None )

				stream = Stream( points )
				gpx = stream.as_gpx()
				tcx = stream.as_tcx(
					average_heart_rate_bpm=act.heartrate,
					calories=act.calories,
					distance_meters=act.distance,
					# id=f'{summary.raw.get( "start_date_local" )}Z',
					intensity='Active', # todo: don't know where to get this from
					maximum_heart_rate_bpm=act.heartrate_max,
					maximum_speed=act.speed_max,
					start_date=act.starttime,
					# trigger_method = 'Distance', # todo: this is not correct
					total_time_seconds=round( act.duration.total_seconds() ),
				)

				act.resources.append( Resource(
					content = gpx.to_xml( prettyprint=True ).encode( 'UTF-8' ),
					type = GPX_TYPE,
				) )
				act.resources.append( Resource(
					content = tostring( tcx.as_xml(), pretty_print=True ),
					type = TCX_TYPE,
				) )

		if len( activities ) == 1: # if there's only one activity, we can return it directly -> main case
			self.remainders = None
			return first( activities )

		elif len( activities ) > 1: # if there's more than one activity, we have to create a multipart activity
			parent_activity = Activity()
			self.remainders = activities # save parts as remainders

			parent_activity.starttime = resource.utc( 'startTime' )
			parent_activity.endtime = resource.utc( 'stopTime' )
			parent_activity.duration = resource.td( 'duration' )
			parent_activity.distance = resource.float( 'distance' )
			parent_activity.heartrate = resource.int( 'averageHeartRate' )
			parent_activity.heartrate_max = resource.int( 'maximumHeartRate' )
			parent_activity.calories = resource.int( 'kiloCalories' )

			# "timeZoneOffset": 60 # todo: convert timezone offset into proper timezone
			parent_activity.timezone = get_timezone().zone
			parent_activity.starttime_local= parent_activity.starttime.astimezone( tzlocal() )
			parent_activity.endtime_local= parent_activity.endtime.astimezone( tzlocal() )

			# append main resource + recordings
			parent_activity.resources.append( resource )
			return parent_activity

		else: # can this happen?
			pass

@importer( type=POLAR_EXERCISE_DATA_TYPE )
class PersonalTrainerImporter( XMLHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=POLAR_EXERCISE_DATA_TYPE, activity_cls=PolarExerciseDataActivity )

	def load_data( self, data: Any, text: Optional[str], content: Optional[bytes], path: Optional[Path], url: Optional[str] ) -> Any:
		xml = super().load_data( data, text, content, path, url )
		root = xml.getroot()
		data = {
			'time': root.find( self._ns( 'calendar-items/exercise/time' ) ).text,
			'type': root.find( self._ns( 'calendar-items/exercise/sport' ) ).text,
			'result_type': root.find( self._ns( 'calendar-items/exercise/sport-results/sport-result/sport' ) ).text,  # should be the same as type
			'duration': root.find( self._ns( 'calendar-items/exercise/sport-results/sport-result/duration' ) ).text,  # should be the same as type
			'distance': root.find( self._ns( 'calendar-items/exercise/sport-results/sport-result/distance' ) ).text,
			'calories': root.find( self._ns( 'calendar-items/exercise/sport-results/sport-result/calories' ) ).text,
			'recording_rate': root.find( self._ns( 'calendar-items/exercise/sport-results/sport-result/recording-rate' ) ).text,
		}
		samples = root.findall( self._ns( 'calendar-items/exercise/sport-results/sport-result/samples/sample' ) )
		for s in samples:
			sample_type = s.find( self._ns( 'type' ) ).text
			sample_values = s.find( self._ns( 'values' ) ).text
			data[('samples', sample_type)] = sample_values.split( ',' )
		return data

	# noinspection PyMethodMayBeStatic
	def _ns( self, s: str ):
		return f'{{{PED_NS}}}' + s.replace( '/', f'/{{{PED_NS}}}' )

@service
class Polar( Service ):

	def __init__( self, **kwargs ):
		super().__init__( **kwargs, display_name=DISPLAY_NAME, base_url=BASE_URL )

		self._session = None
		self._logged_in = False

		self.importer: PolarFlowImporter = PolarFlowImporter()
		self._session_importer = PolarTrainingSessionImporter()
		self.take_importer: PolarFlowTakeoutImporter = PolarFlowTakeoutImporter()
		self.json_handler: JSONHandler = JSONHandler()
		self.gpx_importer = GPXImporter()

	def _link_path( self, pa: Activity, ext: str ) -> Path or None:
		if pa.id:
			utc = pa.utctime
			parent = Path( self._lib_dir, utc.strftime( '%Y/%m/%d' ) )
			# a = self.db.get_activity( pa )
			# if a and a.name:
			#	return Path( parent, f'{utc.strftime( "%H%M%S" )} - {a.name}.polar.{ext}' )  # fully qualified path
			# else:
			return Path( parent, f'{utc.strftime( "%H%M%S" )}.{self.name}.{ext}' )  # fully qualified path
		else:
			return None

	@property
	def login_url( self ) -> str:
		return f'{self.base_url}/login'

	@property
	def ajax_login_url( self ) -> str:
		return f'{self.base_url}/ajaxLogin?_={str( int( current_time() ) )}'

	@property
	def events_url( self ) -> str:
		return f'{self.base_url}/training/getCalendarEvents'

	@property
	def activity_url( self ) -> str:
		return f'{self.base_url}/training/analysis'

	@property
	def export_url( self ) -> str:
		return f'{self.base_url}/api/export/training'

	def events_url_for( self, range_from: datetime, range_to: datetime, year: Optional[int] = None ) -> str:
		if year:
			range_from, range_to = datetime( year, 1, 1 ), datetime( year, 12, 31 )
		if range_from and range_to:
			return f'{self.events_url}?start={range_from.strftime("%d.%m.%Y")}&end={range_to.strftime("%d.%m.%Y")}'
		else:
			return self.all_events_url()

	def all_events_url( self ):
		return f'{self.events_url}?start=1.1.1970&end=1.1.{datetime.utcnow().year + 1}'

	def url_for_id( self, local_id: Union[int, str] ) -> str:
		return f'{self.activity_url}/{local_id}'

	def url_for_resource_type( self, local_id: Union[int, str], type: str ):
		url = None

		if type == POLAR_CSV_TYPE:
			url = f'{self.export_url}/csv/{local_id}'
		elif type == GPX_TYPE:
			url = f'{self.export_url}/gpx/{local_id}'
		elif type == TCX_TYPE:
			url = f'{self.export_url}/tcx/{local_id}'
		elif type == POLAR_HRV_TYPE:
			url = f'{self.export_url}/rr/csv/{local_id}'
		elif type == POLAR_ZIP_GPX_TYPE:
			url = f'{self.export_url}/gpx/{local_id}?compress=true'
		elif type == POLAR_ZIP_TCX_TYPE:
			url = f'{self.export_url}/tcx/{local_id}?compress=true'

		return url

	# FS import
	def supports_fs_import( self, fs: FS | None, path: str | None ) -> bool:
		return any ( [ f for f in fs.walk.files( '/', filter=[ ACCOUNT_PROFILE_GLOB ] ) ] )

	def import_from_fs( self, src_fs: FS, dst_fs: FS, **kwargs ) -> Activities:
		log.debug( f'fetching {self.name} activities from {src_fs}' )
		imported_activities = Activities()

		activity_files = sorted( [ f for f in src_fs.walk.files( '/', filter=[ TRAINING_SESSION_GLOB ] ) ] )
		log.debug( f'found {len( activity_files )} activity files in {src_fs}' )

		if not self.ctx.force:
			log.debug( f'checking db for already existing activities ...' )

			for af, ex in zip_longest( activity_files, existing := [] ):
				if m := TRAINING_SESSION_REGEX.fullmatch( af ):
					uid = UID( f'{self.name}:{m.groups()[1]}' )
					if not self.db.contains_activity( uid ):
						existing.append( af )
			activity_files = existing

			log.debug( f'found {len( activity_files)} activities which do not yet exist in db' )

		for file in activity_files:
			id = TRAINING_SESSION_REGEX.fullmatch( file ).groups()[1]
			uid, src = UID( f'{self.name}:{id}' ), f'{self.name}{file}'
			session_activity = self._session_importer.load_as_activity( fs=src_fs, path=file )
			session_activity.uid = uid

			if not self._session_importer.remainders:
				session = first_true( session_activity.resources, pred=lambda r: r.type == POLAR_SESSION_TYPE )
				gpx = first_true( session_activity.resources, pred=lambda r: r.type == GPX_TYPE )
				tcx = first_true( session_activity.resources, pred=lambda r: r.type == TCX_TYPE )

				# update resource metadata
				for r, ext in zip( [session, gpx, tcx], ['.session.json', '.gpx', '.tcx'] ):
					r.path = path_for_id( id, self.name, f'{id}{ext}' )
					r.uid, r.source = uid, src

				# write resources
				dst_fs.makedirs( dirname( session.path ), recreate=True )
				for r in [session, gpx, tcx]:
					dst_fs.writebytes( r.path, contents=r.content )
					log.debug( f'wrote {len( r.content )} bytes of resource content to {dst_fs}/{r.path}' )
					r.unload()

				imported_activities.append( session_activity )

			else:
				remainders = sorted( self._session_importer.remainders, key=lambda r: r.starttime )

				for i, a in enumerate( remainders ):
					summary = first_true( a.resources, pred=lambda r: r.type == POLAR_SESSION_TYPE )
					gpx = first_true( a.resources, pred=lambda r: r.type == GPX_TYPE )
					tcx = first_true( a.resources, pred=lambda r: r.type == TCX_TYPE )

					# update resource metadata
					for r, ext in zip( [ summary, gpx, tcx ], [ '.session.json', '.gpx', '.tcx' ] ):
						r.path = path_for_id( id, self.name, f'{id}.{i + 1}{ext}' )
						r.uid, r.source = UID( uid.classifier, uid.local_id, part=i + 1 ), src

					# write resources
					dst_fs.makedirs( dirname( summary.path ), recreate=True )
					for r in [summary, gpx, tcx]:
						dst_fs.writebytes( r.path, contents=r.content )
						log.debug( f'wrote {len( r.content )} bytes of resource content to {dst_fs}/{r.path}' )
						r.unload()

					# update activity
					a.uid = UID( uid.classifier, uid.local_id, part=i + 1 )

				# update and write session resource
				session = first_true( session_activity.resources, pred=lambda r: r.type == POLAR_SESSION_TYPE )
				session.path = path_for_id( id, self.name, f'{id}.session.json' )
				session.uid, session.source = uid, src
				dst_fs.writebytes( session.path, contents=session.content )
				log.debug( f'wrote {len( session.content )} bytes of resource content to {dst_fs}/{session.path}' )
				session.unload()

				# update session activity to be multipart
				session_activity.parts = [ ActivityPart( uid=part.uid, gap=part.starttime - session_activity.starttime ) for part in remainders ]
				imported_activities.extend( [ session_activity, *remainders ] )

		return imported_activities

	def login( self ) -> bool:
		if self._logged_in and self._session:
			return self._logged_in

		if not self._session:
			self._session = CachedSession( backend='memory' )

		# noinspection PyUnusedLocal
		response = self._session.get( self.base_url )
		response = self._session.get( self.ajax_login_url )

		try:
			token = BeautifulSoup( response.text, 'html.parser' ).find( 'input', attrs={ 'name': 'csrfToken' } )['value']
		except TypeError:
			token = None

		log.debug( f"CSRF Token: {token}" )

		if token is None:
			echo( "CSRF Token not found" )
			return False

		if not self.cfg_value( 'username' ) and not self.cfg_value( 'password' ):
			log.error( f"application setup not complete for Polar Flow, consider running {APPNAME} setup" )
			sysexit( -1 )#

		data = {
			'csrfToken': token,
			'email': self.cfg_value( 'username' ),
			'password': self.cfg_value( 'password' ),
			'returnUrl': '/'
		}

		# noinspection PyUnusedLocal
		response = self._session.post( self.login_url, headers=HEADERS_LOGIN, data=data )

		self._logged_in = True

		return self._logged_in

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		if kwargs.get( 'from_takeouts', False ):
			return self.take_importer.fetch( fs=self.ctx.takeout_fs( self.name ), existing_uids=kwargs.get( 'existing_uids' ), force=force )

		else:
			try:
				url = self.events_url_for( range_from=kwargs.get( 'range_from' ), range_to=kwargs.get( 'range_to' ) )
				json_list = self.json_handler.load( url=url, headers=HEADERS_API, session=self._session, stream=False )

				return [
					self.importer.save_to_resource(
						content=self.json_handler.save_raw( j ),
						raw=j,
						data=self.importer.load_data( j ),
						uid=f'{self.name}:{ _local_id( j ) }',
						path=f'{_local_id( j )}.json',
						type=POLAR_FLOW_TYPE,
						source=self.url_for_id( _local_id( j ) ),
					) for j in json_list.raw
				]

			except RuntimeError:
				log.error( f'error fetching activity ids' )
				return []

	def download( self, summary: Resource, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		try:
			if not summary.raw:
				load_resource( summary, update_raw=True )
			multipart = _is_multipart_id( summary.raw.get( 'iconUrl' ) )
		except AttributeError:
			multipart = False

		self.login()

		return self.download_multipart_resources( summary ) if multipart else self.download_resources( summary )

	def download_multipart_resources( self, summary: Resource ) -> List[Resource]:
		resources = [
			Resource( uid=summary.uid, type=POLAR_ZIP_GPX_TYPE, path=f'{summary.local_id}.gpx.zip', source=f'{self.export_url}/gpx/{summary.local_id}?compress=true' ),
			Resource( uid=summary.uid, type=POLAR_ZIP_TCX_TYPE, path=f'{summary.local_id}.tcx.zip', source=f'{self.export_url}/tcx/{summary.local_id}?compress=true' ),
		]

		for r in list( resources ):
			try:
				self.download_resource( r )
				resources.extend( decompress_resources( r, self.gpx_importer ) )
			except (CreateFailed, BadZipFile):
				log.debug( f'error fetching resource from {r.source}', exc_info=True )

			if not r.content:
				resources.remove( r )

		return resources

	def download_resources( self, summary: Resource ) -> List[Resource]:
		resources = [
			Resource(
				uid=summary.uid,
				type=POLAR_CSV_TYPE,
				path=f'{summary.local_id}.csv',
				source=f'{self.export_url}/csv/{summary.local_id}'
			),
			Resource(
				uid=summary.uid,
				type=GPX_TYPE,
				path=f'{summary.local_id}.gpx',
				source=f'{self.export_url}/gpx/{summary.local_id}'
			),
			Resource(
				uid=summary.uid,
				type=TCX_TYPE,
				path=f'{summary.local_id}.tcx',
				source=f'{self.export_url}/tcx/{summary.local_id}'
			),
			Resource(
				uid=summary.uid,
				type=POLAR_HRV_TYPE,
				path=f'{summary.local_id}.hrv.csv',
				source=f'{self.export_url}/rr/csv/{summary.local_id}'
			)
		]

		for r in list( resources ):
			try:
				self.download_resource( r )
			except RuntimeError:
				log.error( f'error fetching resource from {r.source}', exc_info=True )

			if not r.content:
				resources.remove( r )

		return resources

	def download_resource( self, resource: Resource, **kwargs ) -> Tuple[Any, int]:
		log.debug( f'downloading resource from {resource.source}' )
		response = self._session.get( resource.source, headers=HEADERS_DOWNLOAD, allow_redirects=True, stream=False )
		resource.content = response.content
		resource.status = response.status_code
		return response.content, response.status_code

	def postprocess_activities( self, activities: List[Activity], resources: List[Resource], **kwargs ) -> List[Activity]:
		if not any( r.type in [POLAR_ZIP_GPX_TYPE, POLAR_ZIP_TCX_TYPE] for r in resources ):
			return activities

		summary = next( (r for r in resources if r.summary), None )
		recordings = [r for r in resources if r.type in [GPX_TYPE, TCX_TYPE]]
		activity = activities[0] # there should be only one activity
		partlist = self.create_partlist( activity, recordings )

		# create separate activity for each part
		for rp in partlist:
			# try to create activity from tcx
			try:
				tcx_resource = next( (tcx for tcx in rp.resources if tcx.type == TCX_TYPE), None )
				new_activity = Service.as_activity_from( tcx_resource )
			except AttributeError:
				try:
					gpx_resource = next( (gpx for gpx in rp.resources if gpx.type == GPX_TYPE), None )
					new_activity = Service.as_activity_from( gpx_resource )
				except AttributeError:
					new_activity = None

			if new_activity:
				# update new activity
				new_activity.starttime=rp.range.start_datetime
				new_activity.starttime_local = rp.range.start_datetime.astimezone( tzlocal() )
				new_activity.endtime=rp.range.end_datetime
				new_activity.endtime_local = rp.range.end_datetime.astimezone( tzlocal() )
				new_activity.uid=f'{summary.uid}#{rp.index}'
				# self.ctx.db.insert_activity( new_activity )
				activities.append( new_activity )
			else:
				log.error( f'unable to find TCX or GPX resources for multipart activity {summary.uid}, please report, this should not happen' )

		# update main activity with parts
		# self.ctx.db.set_field( Query().uids == [activity.uid], 'parts', activity.parts )
		# self.ctx.db.upsert_activity( activity )
		return activities

	# noinspection PyMethodMayBeStatic
	def unzip_resources( self, resources: List[Resource] ) -> List[Resource]:
		unzipped_resources = []
		for r in list( resources ):
			if r.type in [POLAR_ZIP_GPX_TYPE, POLAR_ZIP_TCX_TYPE]:
				unzipped_resources.extend( decompress_resources( r, self.gpx_importer ) )
		return unzipped_resources

	# noinspection PyMethodMayBeStatic
	def create_partlist( self, activity: Activity, resources: List[Resource] ) -> List[ResourcePartlist]:
		ranges: Dict[int, ResourcePartlist] = { }
		for r in resources:
			recording = Service.as_activity_from( r )
			dtr = DateTimeRange( recording.starttime, recording.endtime )

			found_key = None
			for k, v in ranges.items():
				if dtr.is_intersection( v.range ):
					found_key = k
					break

			if found_key is None:
				ranges[len( ranges.keys() )] = ResourcePartlist( resources=[r], range=dtr )
			else:
				ranges.get( found_key ).range.encompass( dtr )
				ranges.get( found_key ).resources.append( r )

		# sort and number parts
		partlists = sorted( ranges.values(), key=lambda pl: pl.start() )

		for index in range( len( partlists ) ):
			partlists[index].index = index + 1
			if index == 0:
				gap = '00:00:00'
			else:
				gap = seconds_to_time( (partlists[index].start() - partlists[index - 1].end()).total_seconds() ).isoformat()
			uids = [f'{activity.uids[0]}?{r.path}' for r in partlists[index].resources]
			activity.parts.append( ActivityPart( gap=time.fromisoformat( gap ), uids=uids ) )

		return partlists

INTRO = f'For Polar Flow we will use their inofficial Web API to download activity data, that\'s why your credentials are needed.'

@setup
def setup( ctx: ApplicationContext, config: Dict, state: Dict ) -> Tuple[Dict, Dict]:
	ctx.console.print( INTRO, width=120 )

	user = Prompt.ask( 'Enter your user name', console=ctx.console, default=config.get( 'username', '' ) )
	password = Prompt.ask( 'Enter your password', console=ctx.console, default=config.get( 'password' ), password=True )

	return { 'username': user, 'password': password }, {}

# --- helper

def _local_id( r: Mapping ) -> int:
	return _raw_id( r )

def _raw_id( r: Mapping ) -> int:
	r = r or { }
	eventType = r.get( 'eventType' )
	if eventType == 'exercise' or eventType == 'fitnessData':
		return r.get( 'listItemId' )
	elif eventType == 'orthostaticTest':
		return int( match( '.*id=(\d+).*', r.get( 'url', '' ) )[1] )
	elif eventType == 'rrTest':
		return int( match( '.*/rr/(\d+)', r.get( 'url', '' ) )[1] )
	return 0

def _type_of( r: Mapping ) -> ActivityTypes:
	if 'iconUrl' not in r:
		return Types.unknown
	id = r.get( 'iconUrl' ).rsplit( '/', 1 )[1]
	return TYPES.get( id, Types.unknown )

def _is_multipart_id( icon_url: str ) -> bool:
	return True if icon_url and (icon_url.endswith( ICON_ID_TRIATHLON ) or icon_url.endswith( ICON_ID_MULTISPORT )) else False

def _multipart_str( self ) -> str:
	if self.multipart:
		return '\u2705'
	else:
		return '\u2716'

def decompress_resources( r: Resource, gpx_importer: GPXImporter ) -> List[Resource]:
	mem_fs = open_fs( 'mem://' )
	mem_fs.writebytes( f'/{r.path}', r.content )
	resources = []

	with mem_fs.openbin( f'/{r.path}' ) as zip_file:
		with ReadZipFS( zip_file ) as zip_fs:
			for f in zip_fs.listdir( '/' ):
				resource = Resource( path=f, content=zip_fs.readbytes( f'/{f}' ), status=200, uid=r.uid, source=r.path )
				resource.type = GPX_TYPE if f.endswith( '.gpx' ) else TCX_TYPE
				gpx_importer.load_as_activity( resource=resource )
				resources.append( resource )

	return resources
