
from datetime import datetime, time, timedelta
from logging import getLogger

from pytest import mark, raises

from tracs.activity import Activities, Activity, ActivityPart, groups
from tracs.activity_types import ActivityTypes
from tracs.core import Metadata, VirtualField
from tracs.pluginmgr import virtualfield
from tracs.resources import Resource, Resources
from tracs.uid import UID

log = getLogger( __name__ )

# noinspection PyUnresolvedReferences
def setup_module( module ):
	import tracs.plugins.rule_extensions
	log.info( 'importing tracs.plugins.rule_extensions' )

def test_activity():
	a = Activity( uid='polar:100' )
	assert a.uid == UID( classifier='polar', local_id=100 )
	assert a.uids == [ 'polar:100' ]
	# assert a.refs() == ['polar:100'] and a.refs( True ) == [UID( 'polar:100' )]
	assert a.classifiers == ['polar']

	assert not a.group
	assert not a.multipart

	# test values
	a = Activity( uid='polar:101', heartrate=150, calories=1000 )
	assert a.values( 'uid', 'heartrate', 'calories', 'speed', 'xyz' ) == ['polar:101', 150, 1000, None, None]

def test_activity_group():
	a = Activity( uid = 'group:101' )
	a.metadata.members = UID.from_strs( [ 'strava:100', 'polar:100', 'polar:100' ] )
	assert a.uid == 'group:101'
	assert a.uids == [ 'polar:100', 'strava:100' ]
#	assert a.refs() == [ 'polar:100', 'strava:100' ]
#	assert a.refs( True ) == [ UID( 'polar:100' ), UID( 'strava:100' ) ]
	assert a.classifiers == [ 'polar', 'strava' ]

	assert a.group
	assert not a.multipart

def test_group_of():
	src1 = Activity(
		id=1,
		name='One',
		uid='polar:1',
		type=ActivityTypes.walk,
		starttime=datetime( 2024, 2, 1, 10, 0, 0 ),
		tags=['a'],
	)
	src2 = Activity(
		id=2,
		name='Two',
		distance=10,
		calories=20,
		uid='polar:2',
		starttime = datetime( 2024, 2, 1, 10, 1, 0 ),
		tags=['b'],
	)

	g1 = Activity( id=3, calories=100, heartrate=100, name='Group One', uid='group:1' )
	g1.metadata.members = UID.from_strs( ['polar:1', 'polar:2'] )

	g2 = Activity( id=4, calories=200, heartrate=200, name='Group Two', uid='group:2' )
	g2.metadata.members = UID.from_strs( ['polar:1', 'polar:2'] )

	# grouping
	group = Activity.group_of(src1, src2 )
	assert group.name == 'One' and group.distance == 10 and group.calories == 20
	assert group.uid == 'group:240201100000' and group.uids == [ 'polar:1', 'polar:2' ]
	assert group.type == ActivityTypes.walk

	# grouping with force
	group = Activity.group_of( src1, src2, force=True )
	assert group.name == 'Two' and group.distance == 10 and group.calories == 20 and group.type == ActivityTypes.walk
	assert group.uid == 'group:240201100000' and group.uids == [ 'polar:1', 'polar:2' ]

	# grouping with ignored_fields
	group = Activity.group_of(src1, src2, ignored_fields=[ 'type' ] )
	assert group.name == 'One' and group.distance == 10 and group.calories == 20
	assert group.uid == 'group:240201100000' and group.uids == [ 'polar:1', 'polar:2' ]
	assert group.type is None

	# grouping with target
	group = Activity.group_of(src1, src2, target=g1 )
	assert group is g1
	assert group.name == 'Group One' and group.distance == 10 and group.calories == 100
	assert group.uid == 'group:240201100000' and group.uids == [ 'polar:1', 'polar:2' ]
	assert group.type == ActivityTypes.walk

	# grouping with target and force
	group = Activity.group_of( src1, src2, target=g2, force=True )
	assert group is g2
	assert group.name == 'Two' and group.distance == 10 and group.calories == 20
	assert group.uid == 'group:240201100000' and group.uids == ['polar:1', 'polar:2']
	assert group.type == ActivityTypes.walk

def test_union_of():
	a1 = Activity(
		id=1,
		name='One',
		distance=10,
		uid='polar:1',
		type=ActivityTypes.walk,
		starttime=datetime( 2024, 2, 1, 10, 0, 0 ),
		tags=['a'],
	)
	a2 = Activity(
		id=2,
		name='Two',
		calories=20,
		uid='polar:2',
		starttime = datetime( 2024, 2, 1, 10, 1, 0 ),
		tags=['b'],
		type=ActivityTypes.run,
	)

	u = Activity.union_of( a1, a2 )
	assert u.name == 'One' and u.distance == 10 and u.calories == 20
	assert u.uid == 'polar:1' and u.uids == [ 'polar:1' ]
	assert u.type == ActivityTypes.walk and u.tags == [ 'a', 'b' ]

	# union with force == True
	u = Activity.union_of( a1, a2, force=True )
	assert u.name == 'Two' and u.distance == 10 and u.calories == 20
	assert u.uid == 'polar:2' and u.uids == ['polar:2']
	assert u.type == ActivityTypes.run and u.tags == ['a', 'b']

def test_activity_part():
	p = ActivityPart( uids=[ 'polar:1234' ] )
	assert p.as_uids == [ UID( classifier='polar', local_id=1234 ) ]
	assert p.classifiers == [ 'polar' ]

	p = ActivityPart( uids=['polar:2345', 'polar:1234' ] )
	assert p.as_uids == [ UID( 'polar:1234' ), UID( 'polar:2345' ) ]
	assert p.classifiers == [ 'polar' ]

	p = ActivityPart( uids=['polar:2345/rec.gpx', 'polar:2345/rec.tcx', 'polar:1234'] )
	assert p.as_uids == [ UID( 'polar:1234' ), UID( 'polar:2345/rec.gpx' ), UID( 'polar:2345/rec.tcx' ) ]
	assert p.as_activity_uids == [ UID( 'polar:1234' ), UID( 'polar:2345' ) ]
	assert p.activity_uids == [ 'polar:1234', 'polar:2345' ]
	assert p.classifiers == [ 'polar' ]

def test_multipart_activity():
	from dateutil.tz import UTC
	swim_start = datetime( 2023, 7, 1, 10, 0, 0, tzinfo=UTC )
	swim_end = datetime( 2023, 7, 1, 10, 30, 0, tzinfo=UTC )
	bike_start = datetime( 2023, 7, 1, 10, 35, 0, tzinfo=UTC )
	bike_end = datetime( 2023, 7, 1, 11, 55, 0, tzinfo=UTC )
	run_start = datetime( 2023, 7, 1, 12, 0, 0, tzinfo=UTC )
	run_end = datetime( 2023, 7, 1, 13, 0, 0, tzinfo=UTC )
	a1 = Activity( uid='polar:101', name='swim', distance=1500, starttime=swim_start, endtime=swim_end )
	a2 = Activity( uid='polar:102', name='bike', distance=40000, starttime=bike_start, endtime=bike_end )
	a3 = Activity( uid='polar:102', name='run', distance=10000, starttime=run_start, endtime=run_end )

	tri = Activity.multipart_of( a1, a2, a3 )

	assert tri.multipart
	assert [ p.gap.seconds for p in tri.parts ] == [ 0, 300, 300 ]
	assert tri.type == ActivityTypes.multisport
	assert tri.distance == 51500
	assert tri.starttime == swim_start
	assert tri.endtime == run_end

	# average is a bit more complicated ...

	bike_start = datetime( 2023, 7, 1, 10, 0, 0, tzinfo=UTC )
	bike_end = datetime( 2023, 7, 1, 12, 0, 0, tzinfo=UTC )
	run_start = datetime( 2023, 7, 1, 12, 0, 0, tzinfo=UTC )
	run_end = datetime( 2023, 7, 1, 13, 0, 0, tzinfo=UTC )
	a1 = Activity( uid='polar:101', name='bike', heartrate=120, starttime=bike_start, endtime=bike_end, duration=timedelta( hours=2 ) )
	a2 = Activity( uid='polar:102', name='run', heartrate=180, starttime=run_start, endtime=run_end, duration=timedelta( hours=1 ) )

	assert Activity.multipart_of( a1, a2 ).heartrate == 140

@mark.skip
def test_multipart_activity2():
	p1 = ActivityPart( uids=['polar:101' ], gap=time( 0, 0, 0 ) )
	p2 = ActivityPart( uids=['polar:102', 'strava:102' ], gap=time( 1, 0, 0 ) )
	a = Activity( parts=[ p1, p2 ] )

	assert a.multipart
	assert a.uids == [ 'polar:101', 'polar:102', 'strava:102' ]
	assert a.as_uids() == [ UID( 'polar:101' ), UID( 'polar:102' ), UID( 'strava:102' ) ]
	assert a.classifiers == [ 'polar', 'strava' ]

	p1 = ActivityPart( uids=['polar:101/swim.gpx' ], gap=time( 0, 0, 0 ) )
	p2 = ActivityPart( uids=['polar:101/bike.gpx' ], gap=time( 1, 0, 0 ) )
	p3 = ActivityPart( uids=['polar:101/run.gpx' ], gap=time( 1, 0, 0 ) )
	a = Activity( parts=[ p1, p2, p3 ] )

	assert a.multipart
	assert a.uids == [ 'polar:101' ]
	assert a.as_uids() == [ UID( 'polar:101' ) ]
	assert a.classifiers == [ 'polar' ]

def test_add():
	src1 = Activity( starttime=datetime( 2022, 2, 22, 7 ), distance=10, duration=timedelta( hours=1 ), heartrate_max=180, heartrate_min=100 )
	src2 = Activity( starttime=datetime( 2022, 2, 22, 8 ), distance=20, duration=timedelta( hours=1, minutes=20 ) )
	src3 = Activity( starttime=datetime( 2022, 2, 22, 9 ), heartrate_max=160, heartrate_min=80 )
	target = src1.add( others=[src2, src3], copy=True )

	assert target.starttime == datetime( 2022, 2, 22, 7 )
	assert target.endtime is None

	assert target.distance == 30
	assert target.ascent is None
	assert target.elevation_max is None

	assert target.duration == timedelta( hours=2, minutes=20 )
	assert target.duration_moving == timedelta( seconds=0 )
	assert target.heartrate_max == 180
	assert target.heartrate_min == 80

def test_activities():
	activities = Activities()
	a1 = Activity( name='a1', uid='a:1' )
	a2 = Activity( name='a2', uid='a:2' )
	a34 = [ Activity( name='a3', uid='a:3' ), Activity( name='a4', uid='a:4' ) ]
	assert activities.add( a1, a2 ) == [1, 2]
	assert activities.add( lst=a34 ) == [3, 4]
	assert len( activities ) == 4

	# convenience constructor
	activities = Activities( a1, a2, lst=a34 )
	assert len( activities ) == 4

	# re-adding will fail
	with raises( KeyError ):
		activities.add( a1 )

	# skip checks
	with raises( KeyError ):
		unchecked = Activities( Activity( id=10 ) )
	unchecked = Activities( Activity( id=10 ), skip_checks=True )
	assert unchecked[0].id is 10 and unchecked[0].uid is None

	# get
	assert activities.get_by_id( 1 ) == a1
	assert activities.get_by_id( 999 ) is None
	assert activities.get_by_uid( 'a:1' ) == a1
	assert activities.get_by_uid( 'a:999' ) is None

	# contains
	assert a1 in activities
	assert UID( 'a:1' ) in activities
	assert not 'something' in activities

	#
	assert activities.ids() == [ 1, 2, 3, 4]
	assert activities.uids() == [ 'a:1', 'a:2', 'a:3', 'a:4' ]

	assert activities.id_map == {
		1: a1, 2: a2, 3: a34[0], 4: a34[1]
	}
	assert activities.uid_map == {
		'a:1': a1, 'a:2': a2, 'a:3': a34[0], 'a:4': a34[1]
	}

	# all
	assert activities.all() == [ a1, a2, *a34 ]
	assert activities.all( sort=True, reverse=True ) == [ a34[1], a34[0], a2, a1 ]
	assert activities.all( sort=lambda a: a.name, reverse=True ) == [ a34[1], a34[0], a2, a1 ]

	# remove
	activities.remove( a34[1] )
	assert activities.get_by_id( 4 ) is None
	del( activities[2] )
	assert activities.get_by_id( 3 ) is None
	activities.remove( a2.uid )
	assert activities.get_by_id( 2 ) is None

	# # replace based on old activity
	# activities.replace( Activity( name='a2', uid='a:2' ), a1 )
	# assert len( activities ) == 1 and activities.idget( 1 ).name == 'a2'
	#
	# # replace based on id
	# activities.replace( Activity( name='a3', uid='a:3' ), id=1 )
	# assert len( activities ) == 1 and activities.idget( 1 ).name == 'a3'
	#
	# # replace based on uid
	# activities.replace( Activity( name='a4', uid='a:4' ), uid='a:3' )
	# assert len( activities ) == 1 and activities.idget( 1 ).name == 'a4'
	#
	# # replace based on id of new activity only
	# activities.replace( Activity( name='a5', uid='a:5', id=1 ) )
	# assert len( activities ) == 1 and activities.idget( 1 ).name == 'a5'
	#
	# # replace based on uid of new activity only
	# activities.replace( Activity( name='a6', uid='a:5' ) )
	# assert len( activities ) == 1 and activities.idget( 1 ).name == 'a6'

def test_iter_activities():
	activities = Activities()
	a1 = Activity(
		name='a1', uid='a:1',
		resources = Resources( Resource( uid='a:1', path='a1.gpx' ), Resource( uid='a:1', path='a1.json' ) )
	)
	a2 = Activity(
		name='a2', uid='a:2',
		resources = Resources( Resource( uid='a:2', path='a2.gpx' ), Resource( path='a2.json' ) ) # no uid in a2.json!!
	)
	g1 = Activity(
		name='g34', uid='g:34',
		metadata = Metadata( members = [ UID( 'a:3' ), UID( 'a:4' ) ] ),
		resources = Resources( Resource( uid='a:3', path='a3.gpx' ), Resource( uid='a:4', path='a4.gpx' ) )
	)

	activities.add( a1 )
	activities.add( a2 )
	activities.add( g1 )

	assert [ it.uid for it in iter( activities ) ] == [ 'a:1', 'a:2', 'g:34' ]
	assert [ it.uid for it in activities.iter() ] == [ 'a:1', 'a:2', 'g:34' ]
	assert [ it.path for it in activities.iter_resources() ] == ['a1.gpx', 'a1.json', 'a2.gpx', 'a2.json', 'a3.gpx', 'a4.gpx']
	assert [ str( uid ) for uid in activities.iter_uids() ] == ['a:1', 'a:2', 'g:34', 'a:3', 'a:4']
	assert [ str( uid ) for uid in activities.iter_resource_uids() ] == [
		'a:1/a1.gpx', 'a:1/a1.json', 'a:2/a2.gpx', 'a:2/a2.json', 'a:3/a3.gpx', 'a:4/a4.gpx'
	]

def test_groups():
	g = Activity( uid='g:1' )
	g.metadata.members=UID.from_strs( [ 'p:1', 's:1' ] )
	ng = Activity( uid='ng:1' )

	assert groups( None ) == []
	assert groups( [g, ng] ) == [g]

def test_resource():
	some_string = 'some string value'
	r = Resource( uid='polar:1', path='content.dat', content=some_string.encode( encoding='UTF-8' ) )
	assert type( r.content ) is bytes and len( r.content ) > 0
	assert r.as_text() == some_string

	r = Resource( uid='polar:1', path='content.dat', text=some_string )
	assert type( r.content ) is bytes and len( r.content ) > 0
	assert r.as_text() == some_string
	assert r.text == some_string

def test_fields( registry ):
	fields = Activity.fields()
	assert next( f for f in fields if f.name == 'name' )
	field_names = Activity.field_names()
	assert 'name' in field_names and '__parent__' not in field_names and 'weekday' not in field_names

	field_names = Activity.field_names( include_internal=True )
	assert 'name' in field_names and '__parent__' in field_names and 'weekday' not in field_names

	field_names = Activity.field_names( include_virtual=True )
	assert 'name' in field_names and '__parent__' not in field_names and 'weekday' in field_names

	assert Activity.field_type( 'name' ) == 'str'
	assert Activity.field_type( 'weekday' ) == int
	assert Activity.field_type( 'noexist' ) is None

@virtualfield
def lower_name( a: Activity ) -> str:
	return a.name.lower()

@virtualfield( name='upper_name' )
def uppercase_name( a: Activity ) -> str:
	return a.name.upper()

@virtualfield( name='title_name', type=str, description='titled activity name' )
def title_name( a: Activity ):
	return a.name.title()

@virtualfield( name='cap_name', description='capitalized activity name', type=str, display_name='Cap Name' )
def capitalized_name( a: Activity ):
	return a.name.capitalize()

def test_virtual_activity_fields( registry ):

	assert 'lower_name' in Activity.__vf__.keys()
	assert 'upper_name' in Activity.__vf__.keys()
	assert 'title_name' in Activity.__vf__.keys()
	assert 'cap_name' in Activity.__vf__.keys()

	vf = Activity.__vf__.get( 'lower_name' )
	assert vf.name == 'lower_name'

	a = Activity(
		name='Afternoon run in Berlin',
		type=ActivityTypes.run,
	)

	assert a.vf.lower_name == 'afternoon run in berlin'
	assert a.vf.upper_name == 'AFTERNOON RUN IN BERLIN'
	assert a.vf.title_name == 'Afternoon Run In Berlin'
	assert a.vf.cap_name == 'Afternoon run in berlin'

	Activity.__vf__['fixed_value'] = VirtualField( 'fixed_value', int, 10 )

	assert a.vf.fixed_value == 10

	with raises( AttributeError ):
		assert a.vf.does_not_exist == 10

	assert a.getattr( 'lower_name' ) == 'afternoon run in berlin'
	assert a.getattr( 'fixed_value' ) == 10
	assert a.getattr( 'does_not_exist', quiet=True ) is None

	with raises( AttributeError ):
		assert a.getattr( 'does_not_exist' ) is None

@virtualfield
def name( a: Activity ) -> str:
	return 'override attempt for run'

# don't allow overriding fields
def test_virtual_activity_field_override( registry ):

	a = Activity( id = 100, name='Run', type=ActivityTypes.run )

	assert 'name' in Activity.field_names( include_virtual=True )
	assert a.name == 'Run' and a.getattr( 'name' ) == 'Run'

def test_formatted_activity_fields():

	a1 = Activity( name='Morning Run in Berlin', type=ActivityTypes.run )
	a2 = Activity( name='Afternoon Walk in Berlin', type=ActivityTypes.walk )

	assert a1.format( 'name' ) == 'Morning Run in Berlin'
	assert a2.format( 'name' ) == 'Afternoon Walk in Berlin'

	Activity.field_formatters()['name'] = lambda s, a, b: s.lower()

	assert a1.format( 'name' ) == 'morning run in berlin'
	assert a2.format( 'name' ) == 'afternoon walk in berlin'
