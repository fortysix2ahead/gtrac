from datetime import datetime

from tracs.activity import Activity
from tracs.group import group_activities2
from tracs.group import ungroup_activities

def test_group_activities():
	a1 = Activity( name='a1', time=datetime( 2022, 2, 22, 10, 0, 0 ), uids=[ 'a:1' ], heartrate_max=180 )
	a2 = Activity( name='a2', time=datetime( 2022, 2, 22, 10, 0, 1 ), uids=[ 'a:2' ], heartrate=150 )
	a3 = Activity( name='a3', time=datetime( 2022, 2, 22, 14, 0, 0 ), uids=[ 'a:3' ] )
	a4 = Activity( name='a4', time=datetime( 2022, 2, 22, 14, 0, 1 ), uids=[ 'a:4' ] )
	a5 = Activity( name='a5', time=datetime( 2022, 2, 22, 14, 0, 2 ), uids=[ 'a:5' ] )
	a6 = Activity( name='a6', time=datetime( 2022, 2, 22, 17, 0, 0 ), uids=[ 'a:6' ] )

	groups = group_activities2( [a3, a2, a6, a1, a4, a5] )

	assert len( groups ) == 2
	g1, g2 = groups
	assert g1.members == [a1, a2]
	assert g2.members == [a3, a4, a5]

	g1.execute()
	assert g1.head.time == a1.time and g1.head.name == a1.name
	assert g1.head.heartrate_max == a1.heartrate_max and g1.head.heartrate == a2.heartrate

def test_ungroup():
	assert db.get( doc_id=1 ).is_group
	assert db.get( doc_id=2 ).grouped_by == 1
	assert db.get( doc_id=3 ).grouped_by == 1
	assert db.get( doc_id=4 ).grouped_by == 1

	ungroup_activities( [db.get( doc_id=1 )], True, True )

	assert db.get( doc_id=1 ) is None
	assert db.get( doc_id=2 ).grouped_by is None
	assert db.get( doc_id=3 ).grouped_by is None
	assert db.get( doc_id=4 ).grouped_by is None
