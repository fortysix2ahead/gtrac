from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from logging import getLogger
from pathlib import Path
from re import match
from sys import exit as sysexit
from time import time as current_time
from typing import Any
from typing import cast
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union
from zipfile import BadZipFile

from bs4 import BeautifulSoup
from click import echo
from datetimerange import DateTimeRange
from dateutil.parser import parse
from dateutil.tz import tzlocal
from dateutil.tz import UTC
from fs import open_fs
from fs.errors import CreateFailed
from fs.zipfs import ReadZipFS
from requests_cache import CachedSession
from rich.prompt import Prompt
from tinydb import Query

from .gpx import GPX_TYPE
from .gpx import GPXImporter
from .handlers import JSON_TYPE
from .handlers import JSONHandler
from .handlers import TCX_TYPE
from .handlers import XMLHandler
from .tcx import TCXImporter
from ..activity import Activity
from ..activity_types import ActivityTypes
from ..activity_types import ActivityTypes as Types
from ..config import ApplicationContext
from ..config import APPNAME
from ..config import console
from ..inout import load_resource
from ..registry import importer
from ..registry import Registry
from ..registry import resourcetype
from ..registry import service
from ..resources import Resource
from ..service import ImportSession
from ..service import Service
from ..utils import seconds_to_time
from ..utils import seconds_to_time as stt

log = getLogger( __name__ )

# general purpose fields/headers/type definitions

SERVICE_NAME = 'polar'
DISPLAY_NAME = 'Polar Flow'

POLAR_CSV_TYPE = 'text/vnd.polar+csv'
POLAR_HRV_TYPE = 'text/vnd.polar.hrv+csv'
POLAR_FLOW_TYPE = 'application/vnd.polar+json'
POLAR_EXERCISE_DATA_TYPE = 'application/vnd.polar.ped+xml'
POLAR_ZIP_GPX_TYPE = 'application/vnd.polar.gpx+zip'
POLAR_ZIP_TCX_TYPE = 'application/vnd.polar.tcx+zip'

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
	'e25370188b9c9b611dcafb6f0028faeb-2015-10-20_13_45_32': Types.hike,
	'f0c9643f1cef947e5621b0b46ab06783-2015-10-20_13_46_12': Types.xcski_free,
	'f4197b0c1a4d65962b9e45226c77d4d5-2015-10-20_13_45_26': Types.swim,
}

@dataclass
class ResourcePartlist:
	index: int = field( default=0 )
	range: DateTimeRange = field( default=None )
	resources: List[Resource] = field( default_factory=list )

	def start( self ) -> datetime:
		return self.range.start_datetime

	def end( self ) -> datetime:
		return self.range.end_datetime

#@resourcetype( type=POLAR_FLOW_TYPE, summary=True )
class PolarActivity( Activity ):

	def __raw_init__( self, raw: Any ) -> None:
		self.raw_id = _raw_id( self.raw )
		self.uid = f'{SERVICE_NAME}:{self.raw_id}'

		self.name = self.raw.get( 'title' )
		self.type = _type_of( self.raw )
		self.time = parse( self.raw['datetime'], ignoretz=True ).replace( tzinfo=tzlocal() ).astimezone( UTC )
		self.localtime = parse( self.raw['datetime'], ignoretz=True ).replace( tzinfo=tzlocal() )
		self.distance = self.raw.get( 'distance' )
		self.duration = stt( self.raw['duration'] / 1000 ) if self.raw.get( 'duration' ) else None
		self.calories = self.raw.get( 'calories' )

	@property
	def is_multipart( self ):
		return _is_multipart_id( self.raw.get( 'iconUrl' ) )

@resourcetype( type=POLAR_FLOW_TYPE, summary=True )
@dataclass
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
	start: Optional[Union[int, str]] = field( default=None )
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

	def get_type( self ) -> ActivityTypes:
		return TYPES.get( self.iconUrl.rsplit( '/', 1 )[1], Types.unknown ) if self.iconUrl else Types.unknown

	def as_activity( self ) -> Activity:
		return Activity(
			local_id=self.local_id,
			# uid = f'{SERVICE_NAME}:{self.local_id}', # todo: remove later?
			uids = [f'{SERVICE_NAME}:{self.local_id}'],
			name = self.title,
			type = self.get_type(),
			time = parse( self.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ).astimezone( UTC ),
			localtime = parse( self.datetime, ignoretz=True ).replace( tzinfo=tzlocal() ),
			distance = self.distance,
			duration = stt( self.duration / 1000 ) if self.duration else None,
			calories = self.calories,
		)

@resourcetype( type=POLAR_CSV_TYPE )
@dataclass
class PolarFlowExerciseCsv:

	pass

@resourcetype( type=POLAR_EXERCISE_DATA_TYPE, summary=True )
class PolarExerciseDataActivity( Activity ):

	def __raw_init__( self, raw: Any ) -> None:
		self.classifier = 'polar'
		self.time = datetime.strptime( self.raw.get( 'time' ), '%Y-%m-%d %H:%M:%S.%f' ).astimezone( UTC )  # 2016-09-15 16:50:27.0
		self.raw_id = int( self.time.strftime( '%y%m%d%H%M%S' ) )
		self.uid = f'{self.classifier}:{self.raw_id}'

@importer( type=POLAR_FLOW_TYPE )
class PolarFlowImporter( JSONHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=POLAR_FLOW_TYPE, activity_cls=PolarFlowExercise )

@importer( type=POLAR_EXERCISE_DATA_TYPE )
class PersonalTrainerImporter( XMLHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=POLAR_EXERCISE_DATA_TYPE, activity_cls=PolarExerciseDataActivity )

	def postprocess_data( self, data: Any, text: Optional[str], content: Optional[bytes], path: Optional[Path], url: Optional[str] ) -> Any:
		xml = super().postprocess_data( data, text, content, path, url )
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

	def __init__( self, base_url=None, **kwargs ):
		super().__init__( name=SERVICE_NAME, display_name=DISPLAY_NAME, **kwargs )
		self._base_url = kwargs.get( 'base_url', BASE_URL )
		self._username = kwargs.get( 'username' )
		self._password = kwargs.get( 'password' )

		self._session = None
		self._logged_in = False

		self.importer: PolarFlowImporter = cast( PolarFlowImporter, Registry.importer_for( POLAR_FLOW_TYPE ) )
		self.json_handler: JSONHandler = cast( JSONHandler, Registry.importer_for( JSON_TYPE ) )

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

	def events_url_for( self, year ) -> str:
		return f'{self.events_url}?start=1.1.{year}&end=31.12.{year}'

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

		if not self._username and not self._password:
			log.error( f"application setup not complete for Polar Flow, consider running {APPNAME} setup" )
			sysexit( -1 )

		data = {
			'csrfToken': token,
			'email': self._username,
			'password': self._password,
			'returnUrl': '/'
		}

		# noinspection PyUnusedLocal
		response = self._session.post( self.login_url, headers=HEADERS_LOGIN, data=data )

		self._logged_in = True

		return self._logged_in

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		if not self.login():
			return []

		try:
			json_resource = self.json_handler.load( url=self.all_events_url(), headers=HEADERS_API, session=self._session )
			resources = []

			for item in json_resource.raw:
				local_id = _local_id( item )
				resources.append( self.importer.save( item, uid=f'{self.name}:{local_id}', resource_path=f'{local_id}.json', resource_type=POLAR_FLOW_TYPE, status=200, source=self.url_for_id( local_id ), summary=True ) )

			return resources

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
				resources.extend( decompress_resources( r ) )
			except (CreateFailed, BadZipFile):
				log.error( f'error fetching resource from {r.source}', exc_info=True )

			if not r.content:
				resources.remove( r )

		return resources

	def download_resources( self, summary: Resource ) -> List[Resource]:
		resources = [
			Resource( uid=summary.uid, type=POLAR_CSV_TYPE, path=f'{summary.local_id}.csv', source=f'{self.export_url}/csv/{summary.local_id}' ),
			Resource( uid=summary.uid, type=GPX_TYPE, path=f'{summary.local_id}.gpx', source=f'{self.export_url}/gpx/{summary.local_id}' ),
			Resource( uid=summary.uid, type=TCX_TYPE, path=f'{summary.local_id}.tcx', source=f'{self.export_url}/tcx/{summary.local_id}' ),
			Resource( uid=summary.uid, type=POLAR_HRV_TYPE, path=f'{summary.local_id}.hrv.csv', source=f'{self.export_url}/rr/csv/{summary.local_id}' )
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
		response = self._session.get( resource.source, headers=HEADERS_DOWNLOAD, allow_redirects=True, stream=True )
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
				new_activity = Registry.importer_for( TCX_TYPE ).as_activity( tcx_resource ).as_activity()
			except AttributeError:
				try:
					gpx_resource = next( (gpx for gpx in rp.resources if gpx.type == GPX_TYPE), None )
					new_activity = Registry.importer_for( GPX_TYPE ).as_activity( gpx_resource ).as_activity()
				except AttributeError:
					new_activity = None

			if new_activity:
				# update new activity
				new_activity.time=rp.range.start_datetime
				new_activity.localtime = rp.range.start_datetime.astimezone( tzlocal() )
				new_activity.time_end=rp.range.end_datetime
				new_activity.localtime_end = rp.range.end_datetime.astimezone( tzlocal() )
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
				unzipped_resources.extend( decompress_resources( r ) )
		return unzipped_resources

	# noinspection PyMethodMayBeStatic
	def create_partlist( self, activity: Activity, resources: List[Resource] ) -> List[ResourcePartlist]:
		ranges: Dict[int, ResourcePartlist] = { }
		for r in resources:
			recording = Registry.importer_for( r.type ).as_activity( r ).as_activity()
			dtr = DateTimeRange( recording.time, recording.time_end )

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
			activity.parts.append( { str( index + 1 ): { 'gap': gap, 'uids': uids } } )

		return partlists

	def setup( self, ctx: ApplicationContext ) -> None:
		console.print( f'For Polar Flow we will use their inofficial Web API to download activity data, that\'s why your credentials are needed.' )

		user = Prompt.ask( 'Enter your user name', default=self.cfg_value( 'username' ) or '' )
		pwd = Prompt.ask( 'Enter your password', default=self.cfg_value( 'password' ) or '', password=True )

		self.set_cfg_value( 'username', user )
		self.set_cfg_value( 'password', pwd )

	def setup_complete( self ) -> bool:
		if self.cfg_value( 'username' ) and self.cfg_value( 'password' ):
			return True
		else:
			return False

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

def decompress_resources( r: Resource ) -> List[Resource]:
	mem_fs = open_fs( 'mem://' )
	mem_fs.writebytes( f'/{r.path}', r.content )
	resources = []

	with mem_fs.openbin( f'/{r.path}' ) as zip_file:
		with ReadZipFS( zip_file ) as zip_fs:
			for f in zip_fs.listdir( '/' ):
				resource = Resource( path=f, content=zip_fs.readbytes( f'/{f}' ), status=200, uid=r.uid, source=r.path )
				resource.type = GPX_TYPE if f.endswith( '.gpx' ) else TCX_TYPE
				Registry.importer_for( resource.type ).load_data( resource )

				resources.append( resource )

	return resources
