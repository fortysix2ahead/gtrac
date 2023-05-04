
from gpxpy.gpx import GPX
from lxml.etree import tostring
from lxml.objectify import ObjectifiedElement
from pytest import mark

from tracs.plugins.gpx import GPX_TYPE
from tracs.plugins.polar import PolarFlowExercise
from tracs.plugins.tcx import Author, Creator, Lap, Plan, TCX_TYPE, Trackpoint, Training, TrainingCenterDatabase
from tracs.registry import Registry
from tracs.plugins.bikecitizens import BIKECITIZENS_TYPE
from tracs.plugins.bikecitizens import BikecitizensActivity
from tracs.plugins.csv import CSV_TYPE
from tracs.plugins.json import JSON_TYPE
from tracs.plugins.xml import XML_TYPE
from tracs.plugins.polar import POLAR_EXERCISE_DATA_TYPE
from tracs.plugins.polar import POLAR_FLOW_TYPE
from tracs.plugins.polar import PolarExerciseDataActivity
from tracs.plugins.strava import STRAVA_TYPE
from tracs.plugins.strava import StravaActivity
from tracs.plugins.tcx import Activity as TCXActivity
from tracs.plugins.waze import WAZE_TYPE
from tracs.plugins.waze import WazeActivity

@mark.file( 'takeouts/waze/waze/2020-09/account_activity_3.csv' )
def test_csv_handler( path ):
	resource = Registry.importer_for( CSV_TYPE ).load( path=path )
	assert type( resource.raw ) is list and len( resource.raw ) == 38

@mark.file( 'templates/polar/2020.json' )
def test_json_importer( path ):
	resource = Registry.importer_for( 'application/json' ).load( path=path )
	assert resource.type == JSON_TYPE
	assert type( resource.content ) is bytes and len( resource.content ) > 0
	assert type( resource.raw ) is list

@mark.file( 'templates/polar/empty.gpx' )
def test_xml_importer( path ):
	resource = Registry.importer_for( XML_TYPE ).load( path=path )
	assert resource.type == XML_TYPE
	assert type( resource.content ) is bytes and len( resource.content ) > 0
	assert resource.raw.getroottree().getroot() is not None
	assert resource.raw.tag == '{http://www.topografix.com/GPX/1/1}gpx'

@mark.file( 'templates/gpx/mapbox.gpx' )
def test_gpx_importer( path ):
	resource = Registry.importer_for( GPX_TYPE ).load( path=path )
	assert type( resource.raw ) is GPX
	assert resource.raw is resource.data

	activity = Registry.importer_for( GPX_TYPE ).load_as_activity( path=path )
	assert activity.time.isoformat() == '2012-10-24T23:29:40+00:00'

@mark.file( 'templates/tcx/sample.tcx' )
def test_tcx_importer( path ):
	resource = Registry.importer_for( TCX_TYPE ).load( path=path )
	assert type( resource.raw ) is ObjectifiedElement
	assert type( resource.data ) is TrainingCenterDatabase

	activity = Registry.importer_for( TCX_TYPE ).load_as_activity( path=path )
	assert activity.time.isoformat() == '2010-06-26T10:06:11+00:00'

def test_tcx_export():
	tcx = TrainingCenterDatabase(
		activities=[
			TCXActivity(
				id='2022-01-24T14:03:42.126Z',
				laps=[
					Lap(
						total_time_seconds=399,
						distance_meters=1000,
						maximum_speed=2.99,
						calories=776,
						average_heart_rate_bpm=160,
						maximum_heart_rate_bpm=170,
						intensity='Active',
						cadence=76,
						trigger_method='Distance',
						trackpoints=[
							Trackpoint(
								time='2023-03-24T14:03:43.126Z',
								latitude_degrees=51.2,
								longitude_degrees=13.7,
								altitude_meters=210.9,
								distance_meters=3.7,
								heart_rate_bpm=133,
								cadence=64,
								sensor_state='Present',
							)
						]
					)
				],
				training=Training(
					virtual_partner='false',
					plan=Plan( type='Workout', interval_workout=False )
				),
				creator=Creator(
					name='Polar Vantage V2',
					unit_id=0,
					product_id=230,
					version_major=4,
					version_minor=1,
					version_build_major=0,
					version_build_minor=0,
				)
			)
		],
		author=Author(
			name='Polar Flow Mobile Viewer',
			build_version_major=0,
			build_version_minor=0,
			lang_id='EN',
			part_number='XXX-XXXXX-XX'
		)
	)
	print()
	print( tostring( tcx.as_xml(), pretty_print=True ).decode( 'UTF-8' ) )

@mark.file( 'libraries/default/polar/1/0/0/100001/100001.json' )
def test_polar_flow_importer( path ):
	importer = Registry.importer_for( POLAR_FLOW_TYPE )
	assert importer.type == POLAR_FLOW_TYPE
	assert importer.activity_cls == PolarFlowExercise

	activity = importer.load_as_activity( path=path )
	assert activity.time.isoformat() == '2011-04-28T15:48:10+00:00'

@mark.skip
@mark.file( 'templates/polar/personal_trainer/20160904.xml' )
def test_polar_ped_importer( path ):
	importer = Registry.importer_for( POLAR_EXERCISE_DATA_TYPE )
	assert importer.type == POLAR_EXERCISE_DATA_TYPE
	assert importer.activity_cls == PolarExerciseDataActivity

	activity = importer.load_as_activity( path=path )
	assert type( activity ) is PolarExerciseDataActivity and activity.uid == 'polar:160904124614'

@mark.file( 'libraries/default/strava/2/0/0/200002/200002.json' )
def test_strava_importer( path ):
	importer = Registry.importer_for( STRAVA_TYPE )
	assert importer.type == STRAVA_TYPE
	assert importer.activity_cls == StravaActivity

	activity = importer.load_as_activity( path=path )
	assert activity.time.isoformat() == '2018-12-16T13:15:12+00:00'

@mark.file( 'libraries/default/bikecitizens/1/0/0/1000001/1000001.json' )
def test_bikecitizens_importer( path ):
	importer = Registry.importer_for( BIKECITIZENS_TYPE )
	assert importer.type == BIKECITIZENS_TYPE
	assert importer.activity_cls == BikecitizensActivity

	activity = importer.load_as_activity( path=path )
	assert activity.time.isoformat() == '2020-05-09T05:03:11+00:00'

@mark.file( 'libraries/default/waze/20/07/12/200712074743/200712074743.txt' )
def test_waze_importer( path ):
	importer = Registry.importer_for( WAZE_TYPE )
	assert importer.type == WAZE_TYPE
	assert importer.activity_cls == WazeActivity

	activity = importer.load_as_activity( path=path )
	assert activity.time.isoformat() == '2020-07-12T05:47:43+00:00'
	assert activity.localtime.isoformat() == '2020-07-12T07:47:43+02:00'
