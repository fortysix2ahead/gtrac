
from datetime import datetime
from datetime import time
from datetime import timedelta
from logging import getLogger

from copy import deepcopy
from csv import writer as csv_writer
from os import system
from re import compile
from typing import Iterable
from typing import List
from typing import Optional
from typing import Union
from urllib.parse import urlparse as parse_url

from dateutil.tz import gettz
from geojson import dump as dump_geojson
from geojson import Feature
from geojson import FeatureCollection
from geojson import LineString
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from tzlocal import get_localzone_name

from .activity import Activity
from .resources import UID
from .resources import Resource
from .config import ApplicationConfig as cfg
from .config import ApplicationContext
from .config import cs
from .db import ActivityDb
from .registry import Registry
from .plugins.gpx import GPX_TYPE
from .plugins.handlers import TCX_TYPE
from .plugins.local import SERVICE_NAME as LOCAL_SERVICE_NAME
from .service import Service
from .ui import diff_table

log = getLogger( __name__ )

TAG_OFFSET_CORRECTION = 'offset'
TAG_TIMEZONE_CORRECTION = 'timezone'

DEFAULT_IMPORTER = 'auto'

MAXIMUM_OPEN = 8

# kepler: https://docs.kepler.gl/docs/user-guides/b-kepler-gl-workflow/a-add-data-to-the-map#geojson
# also nice: https://github.com/luka1199/geo-heatmap

def import_activities( ctx: Optional[ApplicationContext], importer: Optional[str], sources: List[str], **kwargs ):
	# use all registered services if nothing is provided
	# services = [ s for i in importers if ( s := Registry.services.get( i ) ) ]

	sources = sources or Registry.service_names()
	uid_pattern = compile( f'^({"|".join( Registry.service_names() )}):(\d+)$' )

	for src in sources:
		uid = UID( src )

		if uid.denotes_service() and (service := Registry.services.get( src )):
			log.debug( f'importing from service {src}' )
			service.import_activities( ctx=ctx, force=ctx.force, pretend=ctx.pretend, **kwargs )

		elif uid.denotes_activity() and (service := Registry.service_for( uid.classifier )):
			service.import_activities( ctx=ctx, force=ctx.force, pretend=ctx.pretend, uids=[src], **kwargs )

		elif uid.denotes_resource() and (service := Registry.service_for( uid.classifier )):
			raise NotImplementedError

		else:
			# try to use src as path
			try:
				path = Path( Path.cwd(), src ).absolute().resolve()
				if path.exists():
					log.debug( f'attempting to import from path {path}' )
					kwargs['skip_download'] = False
					kwargs['path'] = path

					s = Registry.services.get( importer, Registry.services.get( LOCAL_SERVICE_NAME ) )
					s.import_activities( ctx=ctx, force=ctx.force, pretend=ctx.pretend, **kwargs )
			except RuntimeError:
				log.error( 'unable to import from path', exc_info=True )

				try:
					url = parse_url( src )
				except:
					raise NotImplementedError

def open_activities( activities: List[Activity], db: ActivityDb ) -> None:
	if len( activities ) > MAXIMUM_OPEN:
		log.warning( f'limit of number of activities to open is {MAXIMUM_OPEN}, ignoring the rest of provided {len( activities )} activities' )
		activities = activities[:MAXIMUM_OPEN]

	resource_type = GPX_TYPE # todo: make this configurable

	paths = []

	for a in activities:
		if resources := db.find_resources_of_type( resource_type, a ):
			paths.append( Service.path_for_resource( resources[0] ) )

	paths = [ str( p ) for p in paths ]
	system( 'open ' + ' '.join( paths ) )

		# os.system( "open " + shlex.quote( filename ) )  # MacOS/X
		# os.system( "start " + filename )  # windows

def reimport_activities( activities: List[Activity], include_recordings: bool = False, strategy: str = None, offset: str = None, timezone: str = None, ctx: ApplicationContext = None ):
	force = ctx.force
	log.debug( f'reimporting {len( activities )} activities, with force={force}' )

	try:
		if offset.startswith( '-' ):
			offset = time.fromisoformat( offset.lstrip( '-' ) )
			offset_delta = timedelta( hours=-offset.hour, minutes=-offset.minute, seconds=-offset.second, microseconds=-offset.microsecond )
		else:
			offset = time.fromisoformat( offset.lstrip( '+' ) )
			offset_delta = timedelta( hours=offset.hour, minutes=offset.minute, seconds=offset.second, microseconds=offset.microsecond )

		timezone = gettz( timezone ) if timezone else None

	except (AttributeError, ValueError):
		log.debug( 'unable to parse offset/timezone', exc_info=True )
		offset_delta = None
		timezone = None

	for activity in activities:
		activity_source = deepcopy( activity )
		for uid in activity.uids:
			resources = ctx.db.find_resources( uid )
			# first iteration: import from raw data only
			for r in resources:
				if not r.type in [ GPX_TYPE, TCX_TYPE ]:
					log.debug( f'importing resource of type {r}' )
					imported_activity = load_resource( r, as_activity=True )
					activity.init_from( other=imported_activity )

			# second iteration import from recording when flag is set
			for r in resources:
				if include_recordings and r.type in [ GPX_TYPE, TCX_TYPE ]:
					log.debug( f'importing resource of type {r}' )
					imported_activity = load_resource( r, as_activity=True )
					activity.init_from( other=imported_activity )

		if offset_delta:
			activity.time = activity.time + offset_delta
			activity.tag( TAG_OFFSET_CORRECTION )

		if timezone:
			activity.timezone = timezone.tzname( datetime.utcnow() )
			activity.localtime = activity.time.astimezone( timezone )
			activity.tag( TAG_TIMEZONE_CORRECTION )
		else:
			activity.timezone = get_localzone_name()
			activity.localtime = activity.time.astimezone( gettz( activity.timezone ) )

		if force or _confirm_init( activity_source, activity, ctx.console ):
			ctx.db.update( activity )

def load_all_resources( db: ActivityDb, activity: Activity ) -> None:
	all_resources = []
	for uid in activity.uids:
		all_resources.extend( db.find_resources( uid ) )

	activity.resources = all_resources

def load_resource( resource: Resource, as_activity: bool = False, update_raw: bool = False ) -> Optional[Union[Resource, Activity]]:
	importers = Registry.importers_for( resource.type )
	path = Service.path_for_resource( resource )

	for i in importers:
		if as_activity:
			if activity := i.load_as_activity( path=path ):
				return activity
		else:
			if loaded_resource := i.load( path=path ):
				if update_raw:
					resource.raw = loaded_resource.raw
				return loaded_resource

	log.error( f'unable to load resource {resource.uid}?{resource.path}, no importer found for resource type {resource.type}' )

def _confirm_init( source: Activity, target: Activity, console: Console ) -> bool:
	table = diff_table( as_dict( source, remove_protected=True ), as_dict( target, remove_protected=True ), header=('Field', 'Old Value', 'New Value') )
	if len( table.rows ) > 0:
		console.print( table )
		answer = Confirm.ask( f'Would you like to reimport activity {source.uids[0]}?', default=False )
	else:
		cs.print( f'no difference found during reimport of activity {source.uids[0]}, skipping reimport' )
		answer = False
	return answer

def export_activities( activities: Iterable[Activity], force: bool = False, pretend: bool = False, **kwargs ):
	pass

def export_resources( resources: Iterable[Activity], force: bool = False, pretend: bool = False, **kwargs ):
	pass

def export_csv( activities: Iterable[Activity], output: Path ):
	csv = [['longitude', 'latitude']]

	merged_gpx = None

	for t in merged_gpx.tracks:
		for s in t.segments:
			for p in s.points:
				csv.append( [ p.longitude, p.latitude ] )

	if not output.is_absolute():
		output = Path( Path.cwd(), output )

	if not cfg['pretend'].get():
		with open( output, 'w', encoding='utf8' ) as f:
			cw = csv_writer( f, delimiter=';', lineterminator='\n' )
			cw.writerows( csv )
			log.debug( f'wrote merged csv to {str( output )}' )

def export_geojson( activities: Iterable[Activity], output: Path ):
	features = []
	merged_gpx = None

	for t in merged_gpx.tracks:
		for s in t.segments:
			segment = [(p.longitude, p.latitude) for p in s.points]
			# example: LineString( [ (8.919, 44.4074), (8.923, 44.4075) ] ) -> takes a list of tuples
			geometry = LineString( segment )
			# geometry = MultiLineString( [tuple( segment )] )  # that's messy ... :-(
			properties = {
			#	'time': r.time,
			}
			features.append( Feature( '', geometry, properties ) )

	if not cfg['pretend'].get():
		with open( output, 'w', encoding='utf8' ) as f:
			dump_geojson( FeatureCollection( features ), f )
			log.debug( f'wrote merged geojson to {str( output )}' )

def export_kml( activities, output ):
	pass

def export_gpx( activities: Iterable[Activity], output: Path ):
	#pf = perf_counter()
	merged_gpx = None

	if not output.is_absolute():
		output = Path( Path.cwd(), output )

	if not cfg['pretend'].get():
		with open( output, 'w', encoding='utf8' ) as f:
			f.write( merged_gpx.to_xml() )
			log.debug( f'wrote merged gpx to {str( output )}' )

	#log.info( f'reading gpx files took {perf_counter() - pf}' )

def export_shp( activities, output: str = None ):
	pass
