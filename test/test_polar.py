
from datetime import datetime, timedelta, timezone

from dateutil.tz import tzlocal, UTC
from pytest import mark

from test.helpers import skip_live
from tracs.activity_types import ActivityTypes
from tracs.plugins.polar import BASE_URL, Polar, PolarFitnessTestImporter, PolarFlowImporter, PolarOrthostaticTestImporter, PolarRRRecordingImporter
from tracs.utils import FsPath

importer = PolarFlowImporter()

@mark.file( 'environments/default/db/polar/1/0/0/100001/100001.json' )
def test_exercise( path ):
	resource = importer.load( path )
	pfe = resource.data
	assert pfe.local_id == 100001
	assert pfe.title == '00:25:34;0.0 km'
	assert pfe.type == 'EXERCISE'
	assert pfe.distance == 12000.3
	assert pfe.calories == 456

	pa = importer.as_activity( resource )
	assert pa.type == ActivityTypes.run
	assert pa.starttime == datetime( 2011, 4, 28, 15, 48, 10, tzinfo=timezone.utc )
	assert pa.starttime_local == datetime( 2011, 4, 28, 17, 48, 10, tzinfo=tzlocal() )
	assert pa.duration == timedelta(hours=0, minutes=25, seconds=34, microseconds=900000 )

@mark.file( 'environments/default/db/polar/1/0/0/100012/100012.json' )
def test_fitness_test( fspath: FsPath ):
	importer = PolarFitnessTestImporter()
	test = importer.as_activity( importer.load( path=fspath.path, fs=fspath.fs ) )
	assert test.uid == 'polar:100012'
	assert test.starttime == datetime( 2011, 12, 25, 9, 57, 16, tzinfo=UTC )

@mark.file( 'environments/default/db/polar/1/0/0/100013/100013.json' )
def test_orthostatic( fspath: FsPath ):
	importer = PolarOrthostaticTestImporter()
	test = importer.as_activity( importer.load( path=fspath.path, fs=fspath.fs ) )
	assert test.uid == 'polar:100013'
	assert test.starttime == datetime( 2016, 9, 28, 19, 11, 4, tzinfo=UTC )

@mark.file( 'environments/default/db/polar/1/0/0/100014/100014.json' )
def test_rrrecording( fspath: FsPath ):
	importer = PolarRRRecordingImporter()
	test = importer.as_activity( importer.load( path=fspath.path, fs=fspath.fs ) )
	assert test.uid == 'polar:100014'
	assert test.starttime == datetime( 2017, 1, 16, 20, 34, 58, tzinfo=UTC )

@mark.context( env='live', persist='clone', cleanup=False )
@mark.service( cls=Polar, init=True, register=True )
def test_constructor( service: Polar ):
	assert service.base_url == f'{BASE_URL}'
	assert service.login_url == f'{BASE_URL}/login'
	assert service.ajax_login_url.startswith( f'{BASE_URL}/ajaxLogin?_=' )
	assert service.events_url == f'{BASE_URL}/training/getCalendarEvents'
	assert service.export_url == f'{BASE_URL}/api/export/training'

@skip_live
@mark.context( env='live', persist='clone', cleanup=False )
@mark.service( cls=Polar, init=True, register=True )
def test_live_workflow( service ):
	service.login()
	assert service.logged_in

	fetched = service.fetch( force=False, pretend=False )
	assert len( fetched ) > 0
