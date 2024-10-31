from datetime import datetime, timedelta

from dateutil.tz import tzlocal, tzoffset, UTC

from tracs.activity import Activity, ActivityPart
from tracs.activity_types import ActivityTypes
from tracs.core import Metadata
from tracs.plugins.gpx import GPX_TYPE
from tracs.resources import Resource, Resources
from tracs.uid import UID

# collection of test objects

COMPLETE_ACTIVITY = Activity(
	id=1,
	uid='polar:101',
	starttime=datetime( 2024, 1, 3, 10, 0, 0, tzinfo=UTC ),
	duration=timedelta( hours=2 ),
	type=ActivityTypes.walk,
	location_country='de',
	metadata=Metadata(
		created=datetime( 2024, 1, 4, 10, 0, 0, tzinfo=UTC ),
		modified=datetime( 2024, 1, 4, 11, 0, 0, tzinfo=UTC ),
		favourite=True,
		members=[UID( 'polar:101' ), UID( 'strava:101' )],
	),
	parts=[
		ActivityPart( uid=UID.from_str( 'polar:222#1' ), gap=timedelta( minutes=20 ) ),
		ActivityPart( uid=UID.from_str( 'polar:222#2' ), gap=timedelta( minutes=20 ) )
	],
	resources=Resources(
		Resource(
			name='recording.gpx',
			type=GPX_TYPE,
			path='polar/1/2/3/1234/1234.gpx',
			source='https://polar.com/1234/1234.gpx',
			uid='polar:1234',
		)
	)
)

COMPLETE_ACTIVITY_WITH_RESOURCE_DATA = Activity(
	id=1,
	uid=UID.from_str( 'polar:101' ),
	starttime=datetime( 2024, 1, 3, 10, 0, 0, tzinfo=UTC ),
	duration=timedelta( hours=2 ),
	type=ActivityTypes.walk,
	location_country='de',
	metadata=Metadata(
		created=datetime( 2024, 1, 4, 10, 0, 0, tzinfo=UTC ),
		modified=datetime( 2024, 1, 4, 11, 0, 0, tzinfo=UTC ),
		favourite=True,
		members=[UID( 'polar:101' ), UID( 'strava:101' )],
	),
	parts=[
		ActivityPart( uid=UID.from_str( 'polar:222#1' ), gap=timedelta( minutes=20 ) ),
		ActivityPart( uid=UID.from_str( 'polar:222#2' ), gap=timedelta( minutes=20 ) )
	],
	resources=Resources(
		Resource(
			name='recording.gpx',
			type=GPX_TYPE,
			path='polar/1/2/3/1234/1234.gpx',
			source='https://polar.com/1234/1234.gpx',
			uid=UID.from_str( 'polar:1234' ),
			content=b'<xml></xml>',
			text='<xml></xml>',
			raw={ 'xml': 'some data' },
			data={ 'xml': 'some data' },
		)
	)
)

COMPLETE_ACTIVITY_DICT = {
	'id': 1,
	'uid': 'polar:101',
	'type': 'walk',
	'location_country': 'de',
	'starttime': '2024-01-03T10:00:00+00:00',
	'duration': '02:00:00',
	'metadata': {
		'created': '2024-01-04T10:00:00+00:00',
		'modified': '2024-01-04T11:00:00+00:00',
		'favourite': True,
		'members': ['polar:101', 'strava:101']
	},
	'parts': [
		{ 'gap': '00:20:00', 'uid': 'polar:222#1' },
		{ 'gap': '00:20:00', 'uid': 'polar:222#2' }
	],
	'resources': [
		{
			'name': 'recording.gpx',
			'path': 'polar/1/2/3/1234/1234.gpx',
			'source': 'https://polar.com/1234/1234.gpx',
			'type': 'application/gpx+xml',
			# 'uid': UID( 'polar:1234' ),
			'uid': 'polar:1234'
		}
	]
}

DEFAULT_ONE = Activity(
	id=1,
	name='Unknown Location',
	type=ActivityTypes.xcski,
	starttime=datetime( 2012, 1, 7, 10, 40, 56, tzinfo=UTC ),
	#starttime_local=datetime( 2012, 1, 7, 11, 40, 56, tzinfo=tzlocal() ),
	starttime_local=datetime( 2012, 1, 7, 11, 40, 56, tzinfo=tzoffset(None, 3600) ),
	location_place='Forest',
	uid='group:1',
	metadata=Metadata(
		members=UID.from_strs( ['polar:1234567890', 'strava:12345678', 'waze:20210101010101'] )
	)
)
