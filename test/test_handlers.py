from fs.errors import ResourceNotFound
from fs.osfs import OSFS
from gpxpy.gpx import GPX
from lxml.etree import tostring
from lxml.objectify import ObjectifiedElement
from pytest import mark, raises

from tracs.errors import ResourceImportException
from tracs.plugins.bikecitizens import BIKECITIZENS_TYPE, BikecitizensActivity, BikecitizensImporter
from tracs.plugins.csv import CSV_TYPE, CSVHandler
from tracs.plugins.gpx import GPX_TYPE, GPXImporter
from tracs.plugins.json import JSON_TYPE, JSONHandler
from tracs.plugins.polar import POLAR_EXERCISE_DATA_TYPE, POLAR_FLOW_TYPE, PolarExerciseDataActivity, PolarFlowExercise, PolarFlowImporter
from tracs.plugins.strava import STRAVA_TYPE, StravaActivity, StravaHandler
from tracs.plugins.tcx import Activity as TCXActivity, Author, Creator, Lap, Plan, TCX_TYPE, TCXImporter, Trackpoint, Training, TrainingCenterDatabase
from tracs.plugins.waze import WAZE_TYPE, WazeActivity, WazeImporter
from tracs.plugins.xml import XML_TYPE, XMLHandler
from tracs.registry import Registry

@mark.file( 'templates/polar/2020.json' )
def test_resource_handler( path ):
	handler = JSONHandler() # use json handler instead of base class
	content = b'{"data":1}'
	json = { 'data': 1 }

	assert handler.load_from_content( content ) == content
	assert 'trainingLoadProInterpretation' in handler.load_from_path( path ).decode( 'UTF-8' )
	fs = OSFS( str( path.parent ) )
	assert 'trainingLoadProInterpretation' in handler.load_from_fs( fs, path.name ).decode( 'UTF-8' )
	assert handler.load_raw( content ) == json
	assert handler.load_data( json ) == json

	# unified load method
	assert handler.load( content=content ).data == json
	data = handler.load( path ).data
	assert isinstance( data, list ) and all( [ isinstance( l, dict ) for l in data ] )
	data = handler.load( fs=fs, path=path.name ).data
	assert isinstance( data, list ) and all( [ isinstance( l, dict ) for l in data ] )

	with raises( FileNotFoundError ):
		handler.load( path='/some_non_existing_path' )

	with raises( ResourceNotFound ):
		handler.load( fs=fs, path='some_non_existing_path' )

@mark.file( 'environments/default/takeouts/waze/2020-09/account_activity_3.csv' )
def test_csv_handler( path ):
	handler = CSVHandler()
	assert handler.TYPE == CSV_TYPE

	resource = handler.load( path=path )
	assert resource.type == CSV_TYPE
	assert type( resource.raw ) is list and len( resource.raw ) == 38

@mark.file( 'templates/polar/2020.json' )
def test_json_handler( path ):
	handler = JSONHandler()
	assert handler.TYPE == JSON_TYPE

	resource = handler.load( path=path )
	assert resource.type == JSON_TYPE
	assert type( resource.content ) is bytes and len( resource.content ) > 0
	assert type( resource.raw ) is list

@mark.file( 'templates/polar/empty.gpx' )
def test_xml_importer( path ):
	handler = XMLHandler()
	assert handler.TYPE == XML_TYPE

	resource = handler.load( path=path )
	assert resource.type == XML_TYPE
	assert type( resource.content ) is bytes and len( resource.content ) > 0
	assert resource.raw.getroottree().getroot() is not None
	assert resource.raw.tag == '{http://www.topografix.com/GPX/1/1}gpx'

@mark.file( 'templates/gpx/mapbox.gpx' )
def test_gpx_importer( path ):
	handler = GPXImporter()
	assert handler.TYPE == GPX_TYPE

	resource = handler.load( path=path )
	assert type( resource.raw ) is GPX
	assert resource.raw is resource.data

	activity = handler.load_as_activity( path=path )
	assert activity.starttime.isoformat() == '2012-10-24T23:29:40+00:00'

@mark.file( 'environments/default/takeouts/drivey/drive-20240913-182956.gpx' )
def test_gpx_importer_empty( path ):
	handler = GPXImporter()
	resource = handler.load( path=path )
	assert type( resource.raw ) is GPX
	assert resource.raw is resource.data

	with raises( ResourceImportException ):
		handler.load_as_activity( path=path )

@mark.file( 'templates/tcx/sample.tcx' )
def test_tcx_importer( path ):
	handler = TCXImporter()
	assert handler.TYPE == TCX_TYPE

	resource = handler.load( path=path )
	assert type( resource.raw ) is ObjectifiedElement
	assert type( resource.data ) is TrainingCenterDatabase

	activity = handler.load_as_activity( path=path )
	assert activity.starttime.isoformat() == '2010-06-26T10:06:11+00:00'

@mark.skip
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

@mark.file( 'environments/default/db/polar/1/0/0/100001/100001.json' )
def test_polar_flow_importer( path ):
	importer = PolarFlowImporter()
	assert importer.TYPE == POLAR_FLOW_TYPE
	assert importer.ACTIVITY_CLS == PolarFlowExercise

	resource = importer.load( path )
	assert resource.type == POLAR_FLOW_TYPE
	assert type( resource.data ) == PolarFlowExercise

	activity = importer.load_as_activity( path=path )
	assert activity.starttime.isoformat() == '2011-04-28T15:48:10+00:00'

@mark.skip
@mark.file( 'templates/polar/personal_trainer/20160904.xml' )
def test_polar_ped_importer( path ):
	importer = Registry.importer_for( POLAR_EXERCISE_DATA_TYPE )
	assert importer.type == POLAR_EXERCISE_DATA_TYPE
	assert importer.activity_cls == PolarExerciseDataActivity

	activity = importer.load_as_activity( path=path )
	assert type( activity ) is PolarExerciseDataActivity and activity.uid == 'polar:160904124614'

@mark.file( 'environments/default/db/strava/2/0/0/200002/200002.json' )
def test_strava_importer( path ):
	importer = StravaHandler()
	assert importer.TYPE == STRAVA_TYPE
	assert importer.ACTIVITY_CLS == StravaActivity

	resource = importer.load( path )
	assert resource.type == STRAVA_TYPE
	assert type( resource.data ) == StravaActivity

	activity = importer.load_as_activity( path=path )
	assert activity.starttime.isoformat() == '2018-12-16T13:15:12+00:00'

@mark.file( 'environments/default/db/bikecitizens/1/0/0/1000001/1000001.json' )
def test_bikecitizens_importer( path ):
	importer = BikecitizensImporter()
	assert importer.TYPE == BIKECITIZENS_TYPE
	assert importer.ACTIVITY_CLS == BikecitizensActivity

	resource = importer.load( path )
	assert resource.type == BIKECITIZENS_TYPE
	assert type( resource.data ) == BikecitizensActivity

	activity = importer.load_as_activity( path=path )
	assert activity.starttime.isoformat() == '2020-05-09T05:03:11+00:00'

@mark.file( 'environments/default/db/waze/20/07/12/200712074743/200712074743.txt' )
def test_waze_importer( path ):
	importer = WazeImporter()
	assert importer.TYPE == WAZE_TYPE
	assert importer.ACTIVITY_CLS == WazeActivity

	resource = importer.load( path )
	assert resource.type == WAZE_TYPE
	assert type( resource.data ) == WazeActivity

	activity = importer.load_as_activity( path=path )
	assert activity.starttime.isoformat() == '2020-07-12T05:47:43+00:00'
	assert activity.starttime_local.isoformat() == '2020-07-12T07:47:43+02:00'
