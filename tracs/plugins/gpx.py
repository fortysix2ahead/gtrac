
from dataclasses import dataclass
from dataclasses import field
from logging import getLogger
from typing import Optional

from dateutil.tz import tzlocal
from dateutil.tz import UTC
from gpxpy import parse as parse_gpx
from gpxpy.gpx import GPX

from tracs.activity import Activity
from tracs.protocols import SpecificActivity
from tracs.registry import resourcetype
from tracs.resources import Resource
from tracs.registry import importer
from tracs.handlers import ResourceHandler
from tracs.utils import seconds_to_time

log = getLogger( __name__ )

GPX_TYPE = 'application/gpx+xml'

@resourcetype( type=GPX_TYPE, recording=True )
@dataclass
class GPXActivity:

	gpx: GPX = field( default=None )

	def as_activity( self ) -> Activity:
		return Activity(
			name = self.gpx.name,
			time = self.gpx.get_time_bounds().start_time.astimezone( UTC ),
			time_end = self.gpx.get_time_bounds().end_time.astimezone( UTC ),
			localtime = self.gpx.get_time_bounds().start_time.astimezone( tzlocal() ),
			localtime_end = self.gpx.get_time_bounds().end_time.astimezone( tzlocal() ),
			distance = round( self.gpx.length_2d(), 1 ),
			duration = seconds_to_time( self.gpx.get_duration() ) if self.gpx.get_duration() else None,
			uid = f'gpx:{self.gpx.get_time_bounds().start_time.astimezone( UTC ).strftime( "%y%m%d%H%M%S" )}',
		)

@importer( type=GPX_TYPE )
class GPXImporter( ResourceHandler ):

	def __init__( self ) -> None:
		super().__init__( resource_type=GPX_TYPE, activity_cls=GPXActivity )

	def load_data( self, resource: Resource, **kwargs ) -> None:
		resource.raw = parse_gpx( resource.content )

	def as_activity( self, resource: Resource ) -> Optional[SpecificActivity]:
		return GPXActivity( gpx=resource.raw )
