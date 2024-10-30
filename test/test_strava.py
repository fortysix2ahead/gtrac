
from datetime import datetime, timedelta
from datetime import time
from datetime import timezone

from dateutil.tz import tzlocal
from pytest import mark

from test.helpers import skip_live
from tracs.activity_types import ActivityTypes
from tracs.plugins.strava import Strava, StravaActivity
from tracs.plugins.strava import StravaHandler

@mark.file( 'environments/default/db/strava/2/0/0/200002/200002.json' )
def test_init_from_raw( path ):
	importer = StravaHandler( activity_cls=StravaActivity )
	resource = importer.load( path )
	sa = importer.as_activity( resource )

	assert sa.id is None
	assert sa.classifiers == ['strava']
	assert sa.uid == 'strava:200002'
	assert sa.type == ActivityTypes.run
	assert sa.starttime == datetime( 2018, 12, 16, 13, 15, 12, tzinfo=timezone.utc )
	assert sa.starttime_local == datetime( 2018, 12, 16, 14, 15, 12, tzinfo=tzlocal() )
	assert sa.distance == 8533.7
	assert sa.speed == 2.353
	assert sa.speed_max == 3.1
	assert sa.ascent == 81.0
	assert sa.descent == 81.0
	assert sa.elevation_max == 260.5
	assert sa.elevation_min == 202.4
	assert sa.duration == timedelta( hours=0, minutes=36, seconds=25 )
	assert sa.duration_moving == timedelta( hours=0, minutes=33, seconds=29 )
	assert sa.heartrate == 149
	assert sa.heartrate_min is None
	assert sa.heartrate_max == 171
	assert sa.location_country == 'Germany'

@skip_live
@mark.context( env='live', persist='clone', cleanup=False )
@mark.service( cls=Strava, init=True, register=True )
def test_import( service ):
	activities = service.import_activities( fetch_all=True )
	assert [ a.uid.to_str() for a in activities ] == [
		'strava:8213576551', 'strava:8213576554', 'strava:8213576563', 'strava:8213576615',
		'strava:7973155107', 'strava:7961381195', 'strava:7956459613', 'strava:7956459639'
	]
