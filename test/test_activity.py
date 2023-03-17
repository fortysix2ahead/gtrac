
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone

from dateutil.tz import UTC
from dateutil.tz import tzlocal
from tzlocal import get_localzone_name

from pytest import mark

from tracs.activity import Activity
from tracs.resources import UID
from tracs.resources import Resource
from tracs.activity_types import ActivityTypes

@mark.file( 'libraries/default/activities.json' )
def test_init( json ):
	# empty init
	a = Activity()
	assert a['id'] == 0 and a.id == 0

	a = Activity( doc_id=1 )
	assert a['id'] == 1 and a.id == 1

	a = Activity( {'name': 'Run'}, 1 )
	assert a['id'] == 1 and a.id == 1
	assert a.name == 'Run'

	# init from db document
	a = Activity( json['_default']['1'], 1 )

	assert a.doc_id == 1 and a['doc_id'] == 1
	assert a['id'] == 1 and a.id == 1
	# assert a.type == "run"
	assert a.type == ActivityTypes.run

	# times
	# assert a.time == '2012-10-24T23:29:40+00:00'
	assert a.time == datetime( 2012, 10, 24, 23, 29, 40, tzinfo=UTC )
	# assert a.localtime == '2012-10-24T22:29:40+01:00'
	# assert a.localtime == datetime( 2012, 10, 24, 22, 29, 40, tzinfo=tzlocal() ) # comparison with tzlocal worked before ...
	assert a.localtime == datetime( 2012, 10, 24, 22, 29, 40, tzinfo=timezone( timedelta( seconds=3600 ) ) )

@mark.file( 'libraries/default/polar/1/0/0/100001/100001.json' )
def test_union( json ):
	src1 = Activity( id=1, name='One' )
	src2 = Activity( id=2, distance=10, calories=20 )
	src3 = Activity( id=3, calories=100, heartrate= 100 )

	target = src1.union( [src2, src3] )
	assert target.name == 'One' and target.distance == 10 and target.calories == 20 and target.heartrate == 100
	assert target.id == 1

	src1 = Activity( id=1, name='One' )
	target = src1.union( others=[src2, src3], force=True )
	assert target.name == 'One' and target.distance == 10 and target.calories == 100 and target.heartrate == 100
	assert target.id == 3

	# test constructor
	src1 = Activity( id=1, name='One' )
	target = Activity( others=[src1, src2, src3] )
	assert target.name == 'One' and target.distance == 10 and target.calories == 20 and target.heartrate == 100
	assert target.id == 0

def test_init_from_other_parts():
	src1 = Activity( distance=10, duration=time( 1, 0, 0 ), heartrate_max=180, heartrate_min=100 )
	src2 = Activity( distance=20, duration=time( 1, 20, 0 ) )
	src3 = Activity( heartrate_max=160, heartrate_min=80 )
	target = Activity( other_parts=[src1, src2, src3] )

	assert target.distance == 30
	assert target.ascent is None
	assert target.elevation_max is None

	assert target.duration == time( 2, 20, 0 )
	assert target.duration_moving is None
	assert target.heartrate_max == 180
	assert target.heartrate_min == 80

def test_asdict():
	a = Activity()
	assert a.asdict() == {
		'timezone' : get_localzone_name(),
	}

	assert as_dict( a ) == {
		'timezone' : get_localzone_name(),
	}

	assert as_dict( a, remove_persist=False ) == {
		'dirty'    : False,
		'doc_id'   : 0,
		'id'       : 0,
		'timezone' : get_localzone_name(),
	}

	activity_dict = {
		'classifier': 'polar',
		'doc_id'    : 1,
		'id'        : 1,
		'metadata'  : {},
		'name'      : 'name',
		'raw_id'    : 1,
		'resources' : [Resource( name='one', path='one.gpx', status=100, type='gpx' )],
		'time'      : datetime( 2020, 1, 1, 10, 0, 0, tzinfo=UTC ),
		'type'      : ActivityTypes.run,
		'uid'       : 'test:1'
	}

	assert as_dict( Activity( data=activity_dict ) ) == {
		'classifier': 'polar',
		'name'      : 'name',
		'raw_id'    : 1,
		'time'      : datetime( 2020, 1, 1, 10, 0, 0, tzinfo=UTC ),
		'timezone'  : get_localzone_name(),
		'type'      : ActivityTypes.run,
		'uid'       : 'test:1',
	}

def test_activity_parts():
	activity = Activity()

def test_uid():
	uid = UID( 'polar' )
	assert uid.classifier == 'polar' and uid.local_id is None and uid.path is None
	assert uid.uid == 'polar' and uid.denotes_service()

	uid = UID( 'polar:101' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path is None
	assert uid.uid == 'polar:101' and uid.denotes_activity()

	uid = UID( 'polar:101?recording.gpx' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path == 'recording.gpx'
	assert uid.uid == 'polar:101?recording.gpx' and uid.denotes_resource()

	uid = UID( 'polar:101#2' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.part == 2
	assert uid.uid == 'polar:101#2' and uid.denotes_part()

	assert UID( classifier='polar', local_id=101 ).uid == 'polar:101'
	assert UID( classifier='polar', local_id=101, path='recording.gpx' ).uid == 'polar:101?recording.gpx'
	assert UID( classifier='polar', local_id=101, part=1 ).uid == 'polar:101#1'
	assert UID( classifier='polar', local_id=101, path='recording.gpx', part=1 ).uid == 'polar:101?recording.gpx#1' # works, but does not make sense ...

def test_resource():
	some_string = 'some string value'
	r = Resource( content=some_string.encode( encoding='UTF-8' ) )
	assert type( r.content ) is bytes and len( r.content ) > 0
	assert r.as_text() == some_string

	r = Resource( text=some_string )
	assert type( r.content ) is bytes and len( r.content ) > 0
	assert r.as_text() == some_string
	assert r.text is None # todo: change to throw exception?
