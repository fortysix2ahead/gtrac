from csv import writer as csv_writer
from datetime import datetime, timedelta
from io import StringIO
from typing import List, Tuple
from typing import Optional

from attrs import define, field
from geojson import dump as dump_geojson
from geojson import Feature
from geojson import FeatureCollection
from geojson import LineString
# from geojson import Point as GeojsonPoint
from gpxpy.gpx import GPX
from gpxpy.gpx import GPXTrack
from gpxpy.gpx import GPXTrackPoint
from gpxpy.gpx import GPXTrackSegment
from lxml.etree import Element, SubElement

from tracs.plugins.tcx import Activity, Lap, Trackpoint as TCXTrackPoint, TrainingCenterDatabase
from tracs.plugins.tcx import Lap as TCXLap
from tracs.resources import Resource

# todo: no need to reinvent the wheel: chosse another point class here
@define
class Point:
	time: datetime = field( default=None )
	lat: float = field( default=None )
	lon: float = field( default=None )
	speed: float = field( default=None )
	alt: float = field( default=None )
	distance: float = field( default=None )
	hr: int = field( default=None )

	# init vars
	start: datetime = field( default=None, kw_only=True )
	seconds: int = field( default=None, kw_only=True )
	latlng: Tuple[float, float] = field( default=None, kw_only=True )

	def __attrs_post_init__( self ):
		if self.start and self.seconds is not None:
			self.time = self.start + timedelta( seconds=self.seconds )
		if self.latlng:
			self.lat, self.lon = self.latlng

@define
class Stream:
	points: List[Point] = field( factory=list )
	gpx: GPX = field( default=None, kw_only=True )

	def __attrs_post_init__( self ):
		if self.gpx:
			gpx_points = [p for t in self.gpx.tracks for s in t.segments for p in s.points]
			self.points = [Point( p.time, p.latitude, p.longitude, p.speed ) for p in gpx_points]

	@property
	def length( self ) -> int:
		return len( self.points )

	def as_csv_list( self ) -> List[List[str]]:
		return [[str( p.lon ), str( p.lat )] for p in self.points]

	def as_feature( self ) -> Feature:
		# return [ GeojsonPoint( (p.lon, p.lat) ) for p in self.points ] # todo: check that lat/lon order is correct
		segment = [(p.lon, p.lat) for p in self.points]  # todo: check that lat/lon order is correct
		return Feature( 'id_1', LineString( segment ), properties={ } )

	def as_gpx_track( self ) -> GPXTrack:
		track = GPXTrack()
		points = [GPXTrackPoint( time=p.time, latitude=p.lat, longitude=p.lon, elevation=p.alt, speed=p.speed ) for p in self.points]
		for p, gp in zip( self.points, points ):
			ext = Element( '{gpxtpx}TrackPointExtension' )
			hr = SubElement( ext, '{gpxtpx}hr' )
			hr.text = str( p.hr )

			gp.extensions.append( ext )
		segment = GPXTrackSegment( points )
		track.segments.append( segment )
		return track

	def as_gpx( self, **kwargs ) -> GPX:
		gpx = GPX()

		gpx.creator = 'Tracs'
		gpx.nsmap['gpxtpx'] = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
		gpx.nsmap['gpxx'] = 'http://www.garmin.com/xmlschemas/GpxExtensions/v3'
		gpx.schema_locations = [
			'http://www.topografix.com/GPX/1/1 ',
			'http://www.topografix.com/GPX/1/1/gpx.xsd ',
			'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
			'http://www.garmin.com/xmlschemas/GpxExtensionsv3.xsd',
			'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
			'http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd'
		]

		gpx.tracks.append( self.as_gpx_track() )
		gpx.time = gpx.tracks[0].get_time_bounds().start_time
		gpx.tracks[0].name = kwargs.get( 'track_name' )
		gpx.tracks[0].type = kwargs.get( 'track_type' )
		return gpx

	def as_tcx_lap( self, **kwargs ) -> TCXLap:
		return TCXLap(
			average_heart_rate_bpm=kwargs.get( 'average_heart_rate_bpm' ),
			calories=kwargs.get( 'calories' ),
			distance_meters=kwargs.get( 'distance_meters' ),
			intensity=kwargs.get( 'intensity' ),
			maximum_heart_rate_bpm=kwargs.get( 'maximum_heart_rate_bpm' ),
			maximum_speed=kwargs.get( 'maximum_speed' ),
			start_date=kwargs.get( 'start_date' ),
			total_time_seconds=kwargs.get( 'total_time_seconds' ),
			trigger_method=kwargs.get( 'trigger_method' ),
			trackpoints=[TCXTrackPoint( time=p.time, latitude_degrees=p.lat, longitude_degrees=p.lon, altitude_meters=p.alt, distance_meters=p.distance, heart_rate_bpm=p.hr ) for p in self.points]
		)

	def as_tcx( self, **kwargs ) -> TrainingCenterDatabase:
		return TrainingCenterDatabase(
			activities=[Activity(
				id=kwargs.get( 'id' ),
				laps=[self.as_tcx_lap( **kwargs )]
			)]
		)

def as_streams( resources: List[Resource] ) -> List[Stream]:
	return [Stream( gpx=r.raw ) for r in resources]

def as_csv( streams: List[Stream] ) -> str:
	csv = [['longitude', 'latitude'], *[line for s in streams for line in s.as_csv_list()]]
	io = StringIO()
	writer = csv_writer( io, delimiter=';', lineterminator='\n' )
	writer.writerows( csv )
	return io.getvalue()

def as_gpx( streams: List[Stream] ) -> GPX:
	gpx = GPX()
	gpx.tracks.extend( [s.as_gpx_track() for s in streams] )
	return gpx

def as_feature_collection( streams: List[Stream] ) -> FeatureCollection:
	return FeatureCollection( [s.as_feature() for s in streams] )

def as_str( resources: List[Resource], fmt: str ) -> Optional[str]:
	if fmt == 'csv':
		return as_csv( as_streams( resources ) )
	elif fmt == 'gpx':
		return as_gpx( as_streams( resources ) ).to_xml( prettyprint=False )
	elif fmt == 'geojson':
		io = StringIO()
		dump_geojson( as_feature_collection( as_streams( resources ) ), io )
		return io.getvalue()
	else:
		return None
