
from datetime import datetime

from gpxpy.gpx import GPX
from pytest import mark

from tracs.activity import Activity
from tracs.plugins.gpx import GPX_TYPE
from tracs.plugins.polar import PolarFlowExercise
from tracs.plugins.tcx import TCX_TYPE
from tracs.registry import Registry
from tracs.plugins.bikecitizens import BIKECITIZENS_TYPE
from tracs.plugins.bikecitizens import BikecitizensActivity
from tracs.plugins.handlers import CSV_TYPE
from tracs.plugins.gpx import GPXActivity
from tracs.plugins.handlers import JSON_TYPE
from tracs.plugins.handlers import XML_TYPE
from tracs.plugins.polar import POLAR_EXERCISE_DATA_TYPE
from tracs.plugins.polar import POLAR_FLOW_TYPE
from tracs.plugins.polar import PolarActivity
from tracs.plugins.polar import PolarExerciseDataActivity
from tracs.plugins.strava import STRAVA_TYPE
from tracs.plugins.strava import StravaActivity
from tracs.plugins.tcx import TCXActivity
from tracs.plugins.tcx import Activity as InternalTCXActivity
from tracs.plugins.waze import WAZE_TYPE
from tracs.plugins.waze import WazeActivity

@mark.file( 'templates/waze/account_activity_3.csv' )
def test_csv_handler( path ):
	resource = Registry.importer_for( CSV_TYPE ).load( path=path )
	assert type( resource.raw ) is list and len( resource.raw ) == 25

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

	activity = Registry.importer_for( GPX_TYPE ).load_as_activity( path=path )
	assert type( activity ) is Activity
	assert activity.time.isoformat() == '2012-10-24T23:29:40+00:00'

@mark.file( 'templates/tcx/sample.tcx' )
def test_tcx_importer( path ):
	resource = Registry.importer_for( TCX_TYPE ).load( path=path )
	assert type( resource.raw ) is InternalTCXActivity

	activity = Registry.importer_for( TCX_TYPE ).load_as_activity( path=path )
	assert type( activity ) is Activity
	assert activity.time.isoformat() == '2010-06-26T10:06:11+00:00'

@mark.file( 'libraries/default/polar/1/0/0/100001/100001.json' )
def test_polar_flow_importer( path ):
	importer = Registry.importer_for( POLAR_FLOW_TYPE )
	assert importer.type == POLAR_FLOW_TYPE
	assert importer.activity_cls == PolarFlowExercise

	resource = importer.load( path=path )
	assert type( resource.raw ) is dict

	activity = importer.load_as_activity( path=path )
	assert type( activity ) is PolarFlowExercise and activity.local_id == 100001

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
	assert type( activity ) is StravaActivity and activity.local_id == 200002

@mark.file( 'libraries/default/bikecitizens/1/0/0/1000001/1000001.raw.json' )
def test_bikecitizens_importer( path ):
	importer = Registry.importer_for( BIKECITIZENS_TYPE )
	assert importer.type == BIKECITIZENS_TYPE
	assert importer.activity_cls == BikecitizensActivity

	activity = importer.load_as_activity( path=path )
	assert type( activity ) is BikecitizensActivity and activity.uid == 'bikecitizens:1000001'

@mark.file( 'libraries/default/waze/20/07/12/200712074743/200712074743.raw.txt' )
def test_waze_importer( path ):
	importer = Registry.importer_for( WAZE_TYPE )
	assert importer.type == WAZE_TYPE
	assert importer.activity_cls == WazeActivity

	activity = importer.load_as_activity( path=path )
	assert type( activity ) is WazeActivity and activity.uid == 'waze:200712074743'
