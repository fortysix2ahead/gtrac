
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import time
from logging import getLogger
from typing import Any
from typing import List
from typing import Optional
from typing import Union

from dateutil.parser import parse as parse_dt
from dateutil.tz import tzlocal
from lxml.objectify import fromstring
from lxml.objectify import ObjectPath
from lxml.objectify import ObjectifiedElement

from .handlers import XMLHandler
from ..activity import Activity as TracsActivity
from ..protocols import ActivityProtocol
from ..registry import resourcetype
from ..resources import Resource
from ..registry import document
from ..registry import importer
from ..utils import seconds_to_time

log = getLogger( __name__ )

TCX_TYPE = 'application/tcx+xml'

@dataclass
class Trackpoint:

	time: Union[datetime, str] = field( default=None )
	lat: float = field( default=None )
	lon: float = field( default=None )
	alt: float = field( default=None )
	dist: float = field( default=None )
	hr: float = field( default=None )
	sensor: float = field( default=None )
	cadence: int = field( default=None )

	def __post_init__( self ):
		self.time = parse_dt( self.time ) if type( self.time ) is str else self.time

@dataclass
class Lap:

	start_time: datetime = field( default=None )
	total_time: float = field( default=None )
	distance: float = field( default=None )
	max_speed: float = field( default=None )
	calories: int = field( default=None )
	heartrate: int = field( default=None )
	heartrate_max: int = field( default=None )
	cadence: int = field( default=None )
	intensity: str = field( default=None )
	trigger_method: str = field( default=None )

	points: List[Trackpoint] = field( default_factory=list )

	def __post_init__( self ):
		pass

	def time( self ) -> Optional[datetime]:
		return self.points[0].time if len( self.points ) > 0 else None

	def time_end( self ) -> Optional[datetime]:
		return self.points[-1].time if len( self.points ) > 0 else None

@dataclass
class Activity:

	id: str = field( default=None )

	laps: List[Lap] = field( default_factory=list )

	def distance( self ) -> float:
		return sum( l.distance for l in self.laps )

	def duration( self ) -> time:
		return seconds_to_time( ( self.time_end() - self.time() ).total_seconds() )

	def time( self ) -> Optional[datetime]:
		return self.laps[0].time() if len( self.laps ) > 0 else None

	def time_end( self ) -> Optional[datetime]:
		return self.laps[-1].time_end() if len( self.laps ) > 0 else None

@resourcetype( type=TCX_TYPE, recording=True )
@dataclass
class TCXActivity:

	tcx: Activity = field( default=None )

	def as_activity( self ) -> Activity:
		return TracsActivity(
			distance = self.tcx.distance(),
			duration = self.tcx.duration(),
			time = self.tcx.time(),
			time_end = self.tcx.time_end(),
			localtime = self.tcx.time().astimezone( tzlocal() ),
			localtime_end = self.tcx.time_end().astimezone( tzlocal() ),
			uid = f'tcx:{self.tcx.time().strftime( "%y%m%d%H%M%S" )}',
		)

@importer( type=TCX_TYPE )
class TCXImporter( XMLHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=TCX_TYPE, activity_cls=TCXActivity )

	def load_data( self, resource: Resource, **kwargs ) -> None:
		resource.raw = fromstring( resource.content )
		root: ObjectifiedElement = resource.raw.getroottree().getroot()

		for a in root.Activities.iterchildren( '{*}Activity' ):
			activity = Activity(
				id = find( a, 'Id' )
			)

			for l in a.iterchildren( '{*}Lap' ):
				activity.laps.append( Lap(
					start_time = parse_dt( l.get( 'StartTime' ) ),
					total_time = find( l, 'TotalTimeSeconds' ),
					distance = find( l, 'DistanceMeters' ),
					max_speed = find( l, 'MaximumSpeed' ),
					calories = find( l, 'Calories' ),
					heartrate = find( l, 'AverageHeartRateBpm.Value' ),
					heartrate_max = find( l, 'MaximumHeartRateBpm.Value' ),
					cadence = find( l, 'Cadence' ),
					intensity= find( l, 'Intensity' ),
					trigger_method= find( l, 'TriggerMethod' ),
				) )

				for tp in l.Track.iterchildren( '{*}Trackpoint' ):
					activity.laps[-1].points.append( Trackpoint(
						time = find( tp, 'Time' ),
						lat = find( tp, 'Position.LatitudeDegrees' ),
						lon = find( tp, 'Position.LongitudeDegrees' ),
						alt = find( tp, 'AltitudeMeters' ),
						dist = find( tp, 'DistanceMeters' ),
						hr = find( tp, 'HeartRateBpm.Value' ),
						sensor = find( tp, 'SensorState' ),
						cadence = find( tp, 'Cadence' ),
					) )

			for t in a.iterchildren( '{*}Training' ):
				pass

			for c in a.iterchildren( '{*}Creator' ):
				creator_name = find( c, 'Name' )
				creator_unit_id = find( c, 'UnitId' )
				creator_product_id = find( c, 'ProductID' )
				creator_version_major = find( c, find( a, 'Creator.Version.VersionMajor' ) )
				creator_version_minor = find( c, find( a, 'Creator.Version.VersionMinor' ) )
				creator_build_major = find( c, find( a, 'Creator.Version.BuildMajor' ) )
				creator_build_minor = find( c, find( a, 'Creator.Version.BuildMinor' ) )

			resource.raw = activity

	def as_activity( self, resource: Resource ) -> Optional[ActivityProtocol]:
		return TCXActivity( tcx=resource.raw )

# helper

def find( element: ObjectifiedElement, sub_element: str ) -> Any:
	try:
		return ObjectPath( f'.{sub_element}' ).find( element ).pyval
	except AttributeError:
		return None
