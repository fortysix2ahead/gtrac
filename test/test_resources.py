from pytest import mark, raises

from tracs.resources import Resource, Resources, ResourceType, ResourceTypes
from tracs.uid import UID

def test_resource_type():
	rt = ResourceType( 'application/xml' )
	assert rt.suffix == 'xml' and rt.extension() == 'xml'

	rt = ResourceType( 'application/gpx+xml' )
	assert rt.subtype == 'gpx' and rt.suffix == 'xml' and rt.extension() == 'gpx'

	rt = ResourceType( 'application/vnd.polar.flow+json' )
	assert rt.subtype == 'flow' and rt.suffix == 'json' and rt.vendor == 'polar' and rt.extension() == 'flow.json'

	rt = ResourceType( 'application/vnd.polar+csv' )
	assert rt.suffix == 'csv' and rt.vendor == 'polar' and rt.extension() == 'csv'

	rt = ResourceType( 'application/vnd.polar.flow+csv' )
	assert rt.subtype == 'flow' and rt.suffix == 'csv' and rt.vendor == 'polar' and rt.extension() == 'flow.csv'

	rt = ResourceType( 'application/vnd.polar.ped+xml' )
	assert rt.subtype == 'ped' and rt.suffix == 'xml' and rt.vendor == 'polar' and rt.extension() == 'ped.xml'

	rt = ResourceType( 'application/vnd.polar.gpx+zip' )
	assert rt.subtype == 'gpx' and rt.suffix == 'zip' and rt.vendor == 'polar' and rt.extension() == 'gpx.zip'

	assert ResourceType( 'application/fit' ).extension() == 'fit'
	assert ResourceType( 'application/vnd.bikecitizens+json' ).extension() == 'json'
	assert ResourceType( 'application/vnd.bikecitizens.rec+json' ).extension() == 'rec.json'
	assert ResourceType( 'application/vnd.polar+json' ).extension() == 'json'
	assert ResourceType( 'application/vnd.strava+json' ).extension() == 'json'
	assert ResourceType( 'application/vnd.waze+txt' ).extension() == 'txt'
	assert ResourceType( 'application/vnd.polar.hrv+txt' ).extension() == 'hrv.txt'
	assert ResourceType( 'application/gpx+xml' ).extension() == 'gpx'
	assert ResourceType( 'application/vnd.polar.ped+xml' ).extension() == 'ped.xml'
	assert ResourceType( 'application/tcx+xml' ).extension() == 'tcx'
	assert ResourceType( 'application/vnd.polar+csv' ).extension() == 'csv'
	assert ResourceType( 'application/vnd.polar.hrv+csv' ).extension() == 'hrv.csv'

def test_resource_types():
	# setup
	ResourceTypes.inst().clear()
	ResourceTypes.inst()[rt.type] = ( rt := ResourceType( 'application/vnd.polar+json', summary=True ) )
	ResourceTypes.inst()[rt.type] = ( rt := ResourceType( 'application/gpx+xml', recording=True ) )
	ResourceTypes.inst()[rt.type] = ( rt := ResourceType( 'image/jpeg', image=True ) )

	# actual test
	assert len( ResourceTypes.inst() ) == 3
	assert ResourceTypes.summaries() == [ ResourceType( 'application/vnd.polar+json', summary=True ) ]
	assert ResourceTypes.recordings() == [ ResourceType( 'application/gpx+xml', recording=True ) ]
	assert ResourceTypes.images() == [ ResourceType( 'image/jpeg', image=True ) ]

def test_resource():
	# creation with separate uid and path arguments
	r = Resource( name='recording', type='application/gpx+xml', path='recording.gpx', uid='polar:1001' )
	assert r.uid == 'polar:1001' and r.uid == UID( 'polar:1001' )
	assert r.classifier == 'polar'
	assert r.local_id == 1001 and r.local_id_str == '1001'
	assert r.uidpath == 'polar:1001/recording.gpx'

	# path can also be integrated into uid
	r = Resource( uid='polar:1001/recording.gpx' )
	assert r.uid == 'polar:1001'
	assert r.classifier == 'polar'
	assert r.local_id == 1001 and r.local_id_str == '1001'
	assert r.uidpath == 'polar:1001/recording.gpx'

	# creation with relative path
	r = Resource( name='recording', type='application/gpx+xml', path='polar/1/0/0/1001/recording.gpx', uid='polar:1001' )
	assert r.uid == 'polar:1001' and r.uid == UID( 'polar:1001' )
	assert r.classifier == 'polar'
	assert r.local_id == 1001 and r.local_id_str == '1001'
	assert r.fpath == 'recording.gpx'
	assert r.uidpath == 'polar:1001/recording.gpx'

	# this works, but is not supposed to be used
	r = Resource( uid=UID( classifier='polar', local_id=1001, path='recording.gpx' ) )
	assert r.uid == 'polar:1001' and r.path == 'recording.gpx'

	# resource without a proper uid/path is allowed, this is used by resource handlers which read from an external URL
	Resource()
	Resource( path='recording.gpx' )

	with raises( AttributeError ):
		Resource( uid='polar:1001' ) # path missing: not allowed
	with raises( AttributeError ):
		Resource( uid='polar', path='recording.gpx' ) # local_id missing: not allowed

	# evolve
	r = Resource( path='recording.gpx', content=b'0123', text='0123', raw={ 'data': '0123' }, data={ 'data': '0123' } )
	e = r.evolve()
	assert r.path == e.path
	assert [e.content, e.text, e.raw, e.data] == [None, None, None, None]

def test_resources():
	r1 = Resource( uid='polar:1234', name='test1.gpx', type='application/gpx+xml', path='test1.gpx' )
	r2 = Resource( uid='strava:1234', name='test2.gpx', type='application/gpx+xml', path='test2.gpx' )
	r3 = Resource( uid='polar:1234', name='test1.json', type='application/vnd.polar+json', path='test1.json' )
	r4 = Resource( uid='strava:1234', name='test2.json', type='application/vnd.polar+json', path='test2.json' )
	r5 = Resource( uid='polar:1234', name='title.jpg', type='image/jpeg', path='title.jpeg' )

	rl = Resources( r1, r2, r3, r4 )
	rl.append( r5 )

	assert len( rl ) == 5

	rl = Resources( lst = [r1, r2, r3, r4, r5] )
	assert len( rl ) == 5

	rl = Resources( lists = [Resources( r1, r2 ), Resources( r3, r4, r5 )] )
	assert len( rl ) == 5

	rl = Resources.from_list( Resources( r1, r2 ), Resources( r3, r4, r5 ) )
	assert len( rl ) == 5

	assert rl.all() == [r1, r2, r3, r4, r5]
	assert rl.all_for( uid=r1.uid ) == [r1, r3, r5]
	assert rl.all_for( path=r1.path ) == [r1]
	assert rl.all_for( uid=r1.uid, path=r1.path ) == [r1]

	r1a = Resource( uid='polar:1234', name='test1.gpx', type='application/gpx+xml', path='test1.gpx' ) # copy of r1
	assert r1a in rl
	r1a.path = 'other.gpx'
	assert r1a not in rl

	# iterators
	assert [ r for r in rl ] == [ r1, r2, r3, r4, r5 ]
	assert rl.iter_for( 'polar:1234/something_to_be_removed' ) == [ r1, r3, r5 ]
	assert rl.iter_types( ['application/gpx+xml'] ) == [ r1, r2 ]
	assert rl.iter_for( 'polar:1234' ).iter_types( ['application/gpx+xml'] ) == [ r1 ]

	assert rl.iter_uids() == [
		'polar:1234/test1.gpx',
		'strava:1234/test2.gpx',
		'polar:1234/test1.json',
		'strava:1234/test2.json',
		'polar:1234/title.jpeg',
	]
	assert rl.iter_uids_for( 'polar:1234/something_to_be_removed' ) == [
		'polar:1234/test1.gpx',
		'polar:1234/test1.json',
		'polar:1234/title.jpeg',
	]
	assert rl.iter_uid_heads() == ['polar:1234', 'strava:1234']
	assert rl.iter_paths() == ['test1.gpx', 'test2.gpx', 'test1.json', 'test2.json', 'title.jpeg']
