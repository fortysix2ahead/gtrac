from cattrs.preconf.orjson import make_converter
from cattrs.strategies import use_class_methods

from tracs.uid import UID

def test_uid():
	uid = UID( 'polar' )
	assert uid.classifier == 'polar' and uid.local_id is None and uid.path is None
	assert uid.uid == 'polar' and uid.denotes_service()
	assert uid.as_tuple == ('polar', None) and uid.as_triple == ( 'polar', None, None )

	uid = UID( 'polar:' )
	assert uid.classifier == 'polar' and uid.local_id is None and uid.path is None
	assert uid.uid == 'polar' and uid.denotes_service()
	assert uid.as_tuple == ('polar', None) and uid.as_triple == ( 'polar', None, None )

	uid = UID( 'polar:101' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path is None
	assert uid.uid == 'polar:101' and uid.denotes_activity()
	assert uid.as_tuple == ('polar', 101) and uid.as_triple == ( 'polar', 101, None )

	# is there still a need for those special cases?
	# special cases for convenience: allow path parameter + allow overwriting
	# uid = UID( 'polar:101', path='recording.gpx' )
	# assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path == 'recording.gpx'
	# assert uid.uid == 'polar:101/recording.gpx' and uid.denotes_resource()
	# assert uid.as_tuple == ('polar', 101) and uid.as_triple == ('polar', 101, 'recording.gpx')

	# special cases for convenience: allow overwriting
	# uid = UID( 'polar:101/file.gpx', path='recording.gpx' )
	# assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path == 'recording.gpx'
	# assert uid.uid == 'polar:101/recording.gpx' and uid.denotes_resource()
	# assert uid.as_tuple == ('polar', 101) and uid.as_triple == ('polar', 101, 'recording.gpx')

	uid = UID( 'polar:101/recording.gpx' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path == 'recording.gpx'
	assert uid.uid == 'polar:101/recording.gpx' and uid.denotes_resource()
	assert uid.as_tuple == ('polar', 101) and uid.as_triple == ( 'polar', 101, 'recording.gpx' )

	uid = UID( 'polar:101#2' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.part == 2
	assert uid.uid == 'polar:101#2' and uid.denotes_part()
	assert uid.as_tuple == ('polar', 101) and uid.as_triple == ( 'polar', 101, None )

	# works, but does not make sense
	uid = UID( 'polar:101/recording.gpx#2' )
	assert uid.classifier == 'polar' and uid.local_id == 101 and uid.path == 'recording.gpx' and uid.part == 2
	assert uid.uid == 'polar:101/recording.gpx#2'
	assert uid.as_tuple == ('polar', 101) and uid.as_triple == ( 'polar', 101, 'recording.gpx' )

	assert UID( classifier='polar' ).uid == 'polar'
	assert UID( classifier='polar', local_id=101 ).uid == 'polar:101'
	assert UID( classifier='polar', local_id=101, path='recording.gpx' ).uid == 'polar:101/recording.gpx'
	assert UID( classifier='polar', local_id=101, part=1 ).uid == 'polar:101#1'
	# works, but does not make sense
	assert UID( classifier='polar', local_id=101, path='recording.gpx', part=1 ).uid == 'polar:101/recording.gpx#1'

def test_eq():
	uid1 = UID( 'polar:101/recording.gpx' )
	uid2 = UID( 'polar:101/recording.gpx' )
	uid3 = UID( 'polar:102/recording.gpx' )
	uid4 = 'polar:102/recording.gpx'

	assert uid1 == uid2
	assert uid1 == 'polar:101/recording.gpx'
	assert 'polar:101/recording.gpx' == uid1
	assert uid1 != uid3 and uid1 != uid4

def test_lt():
	uid1 = UID( 'polar:101' )
	uid2 = UID( 'polar:102' )
	uid3 = 'strava:101'

	assert uid1 < uid2
	assert uid2 > uid1
	assert uid2 < uid3
	assert uid3 > uid2

	assert sorted( [uid2, uid3, uid1] ) == [uid1, uid2, uid3]

def test_serialize():
	uid_str = 'polar:101/recording.gpx#1'
	uid = UID( uid_str )

	assert uid.to_str() == uid_str and UID.from_str( uid_str ) == uid
