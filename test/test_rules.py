from datetime import datetime, time
from logging import getLogger
from re import match
from typing import cast

from dateutil.tz import tzlocal, UTC
from pytest import mark, raises
from rule_engine import Context, EvaluationError, resolve_attribute, Rule, RuleSyntaxError, SymbolResolutionError

from tracs.core import Metadata
from tracs.activity import Activity, ActivityPart
from tracs.activity_types import ActivityTypes
from tracs.plugins.rule_extensions import TIME_FRAMES as TIME_FRAMES_EXT
from tracs.rules import DATE_PATTERN, DATE_RANGE_PATTERN, FUZZY_DATE_PATTERN, FUZZY_TIME_PATTERN, INT_LIST, INT_PATTERN, KEYWORD_PATTERN, LIST_PATTERN, \
	parse_date_range_as_str, RANGE_PATTERN, RULE_PATTERN, TIME_PATTERN, TIME_RANGE_PATTERN
from uid import UID

log = getLogger( __name__ )

NOW = datetime.utcnow()
ATTRIBUTE_CONTEXT = Context( resolver=resolve_attribute )

TIME_FRAMES_EXT_FROM_PLUGIN = TIME_FRAMES_EXT # this is to make sure the rule_extensions plugin is loaded

A1 = Activity(
	id=1000,
	name="Berlin",
	description="Morning Run in Berlin",
	type=ActivityTypes.run,
	starttime=datetime( 2023, 1, 13, 10, 0, 42, tzinfo=UTC ),
	starttime_local=datetime( 2023, 1, 13, 10, 0, 42, tzinfo=UTC ).astimezone( tzlocal() ),
	heartrate=160,
	metadata=Metadata(
		members=UID.from_strs( ['polar:123456', 'strava:123456'] )
	)
)

d2 = {
	'heartrate': 180,
	'time': datetime.utcnow(),
	'tags': ['morning', 'salomon', 'tired'],
	'uids': ['polar:1234', 'strava:3456']
}

a2 = Activity(
	heartrate=180,
	starttime=datetime( 2023, 11, 11, 10, 0, 42, tzinfo=UTC ),
	tags=['morning', 'salomon', 'tired'],
	metadata = Metadata(
		members=UID.from_strs( ['polar:1234', 'strava:3456'] )
	)
)

def test_rule_engine():
	# plain case does not work with classes, only with dictionaries
	with raises( SymbolResolutionError ):
		assert Rule( 'heartrate == 180' ).matches( a2 )
	assert Rule( 'heartrate == 180' ).matches( d2 )
	assert Rule( 'heartrate == 180', context=ATTRIBUTE_CONTEXT ).matches( a2 )
	assert not Rule( 'heartrate_max == 180', context=ATTRIBUTE_CONTEXT ).matches( a2 )

	# how to get around a SymbolResolutionError:
	context = Context( default_value=None )
	rule = Rule( 'year == 2023', context=context )
	assert not rule.matches( a2 )

	# how to use a custom resolver
	def resolve_year( thing, name ):
		if name == 'year':
			return cast( Activity, thing ).starttime.year
		elif name == 'classifiers' and type( thing ) is tuple:
			return list( map( lambda s: s.split( ':', 1 )[0], thing ) )
		else:
			return resolve_attribute( thing, name )

	context = Context( default_value=None, resolver=resolve_year )
	assert Rule( 'heartrate == 180', context=context ).matches( a2 )
	assert Rule( 'year == 2023', context=context ).matches( a2 )
	assert Rule( 'heartrate == 180 and year == 2023', context=context ).matches( a2 )
	assert not Rule( 'heartrate == 170 and year == 2023', context=context ).matches( a2 )

	assert Rule( '"tired" in tags', context=context ).matches( a2 )
	assert not Rule( '"evening" in tags', context=context ).matches( a2 )

	assert Rule( '"polar:1234" in uids', context=context ).matches( a2 )
	assert not Rule( '"polar" in uids', context=context ).matches( a2 )
	assert Rule( '"polar" in uids.classifiers', context=context ).matches( a2 )

def test_rule_pattern():
	# special cases

	# numbers are allowed and are treated as ids
	assert INT_PATTERN.match( '1000' )

	# list are comma-separated and need to contain more than one element
	assert match( LIST_PATTERN, '100,101')
	assert match( LIST_PATTERN, '100,101,102')
	assert match( LIST_PATTERN, 'a,b,c')
	assert not match( LIST_PATTERN, '100')
	assert not match( LIST_PATTERN, '100,101,102,')

	assert INT_LIST.match( '1000,1001,1002' )
	assert not INT_LIST.match( '1000,1001,1002,' )

	# ranges are separated by two dots, where start and end might be missing
	assert match( RANGE_PATTERN, '1000..1002' )
	assert match( RANGE_PATTERN, '1000..' )
	assert match( RANGE_PATTERN, '..1002' )
	assert match( RANGE_PATTERN, '100.4..100.9' )
	assert match( RANGE_PATTERN, '2020-01-01..2020-06-30' )
	assert match( RANGE_PATTERN, '10:00:00..11:00:00' )

	# date ranges
	assert DATE_RANGE_PATTERN.fullmatch( '2020..2020' )
	assert DATE_RANGE_PATTERN.fullmatch( '2020-01..2020-06' )
	assert DATE_RANGE_PATTERN.fullmatch( '2020-01-01..2020-06-30' )
	assert DATE_RANGE_PATTERN.fullmatch( '2020..' )
	assert DATE_RANGE_PATTERN.fullmatch( '2020-01..' )
	assert DATE_RANGE_PATTERN.fullmatch( '2020-01-01..' )
	assert DATE_RANGE_PATTERN.fullmatch( '..2020' )
	assert DATE_RANGE_PATTERN.fullmatch( '..2020-06-30' )
	assert DATE_RANGE_PATTERN.fullmatch( '..2020-06' )

	# time ranges
	assert TIME_RANGE_PATTERN.fullmatch( '09..11' )
	assert TIME_RANGE_PATTERN.fullmatch( '09:05..11:05' )
	assert TIME_RANGE_PATTERN.fullmatch( '09:05:36..11:05:55' )
	assert TIME_RANGE_PATTERN.fullmatch( '09..' )
	assert TIME_RANGE_PATTERN.fullmatch( '09:05..' )
	assert TIME_RANGE_PATTERN.fullmatch( '09:05:36..' )
	assert TIME_RANGE_PATTERN.fullmatch( '..11' )
	assert TIME_RANGE_PATTERN.fullmatch( '..11:05' )
	assert TIME_RANGE_PATTERN.fullmatch( '..11:05:55' )

	# dates always contain year, month and day
	assert match( DATE_PATTERN, '2022-03-13' )
	assert not match( DATE_PATTERN, '2022' )
	assert not match( DATE_PATTERN, '2022-03' )

	# fuzzy dates may omit month and day and are treated as ranges
	assert match( FUZZY_DATE_PATTERN, '2022' ) # beware: this is also a number!
	assert match( FUZZY_DATE_PATTERN, '2022-03' )
	assert match( FUZZY_DATE_PATTERN, '2022-03-13' )

	# same is true for times: always contain hours, minutes and seconds
	assert match( TIME_PATTERN, '13:10:42' )
	assert not match( TIME_PATTERN, '13' )
	assert not match( TIME_PATTERN, '13:10' )

	# fuzzy times are also treated as ranges
	assert match( FUZZY_TIME_PATTERN, '13' )
	assert match( FUZZY_TIME_PATTERN, '13:10' )
	assert match( FUZZY_TIME_PATTERN, '13:10:42' )

	# keywords must begin with a letter and may contain letters, numbers, dashes und underscores

	assert match( KEYWORD_PATTERN, 'polar' )
	assert match( KEYWORD_PATTERN, 'polar_2022' )
	assert match( KEYWORD_PATTERN, 'polar-2022' )
	assert match( KEYWORD_PATTERN, 'Polar22' )
	assert not match( KEYWORD_PATTERN, '1Polar22' )

def test_rule_pattern_2():

	# normal expressions

	# empty value is allowed
	assert match( RULE_PATTERN, 'id:' )

	assert match( RULE_PATTERN, 'id:1000' )
	assert match( RULE_PATTERN, 'ID:1000' )

	assert match( RULE_PATTERN, 'id:1000,1001,1002' )
	assert match( RULE_PATTERN, 'id:1000..1002' )

	assert match( RULE_PATTERN, 'date:2020-01-15..2021-09-01' )
	assert match( RULE_PATTERN, 'date:2020..2021-09' )

	assert match( RULE_PATTERN, 'id=1000' )
	assert match( RULE_PATTERN, 'id==1000' )
	assert match( RULE_PATTERN, 'id!=1000' )
	assert match( RULE_PATTERN, 'id>1000' )
	assert match( RULE_PATTERN, 'id>=1000' )
	assert match( RULE_PATTERN, 'id<1000' )
	assert match( RULE_PATTERN, 'id<=1000' )

	assert match( RULE_PATTERN, 'name:berlin' )
	assert match( RULE_PATTERN, 'name=Berlin' )
	assert match( RULE_PATTERN, 'name="Morning Run"' )
	assert match( RULE_PATTERN, 'name!="Morning Run"' )
	assert match( RULE_PATTERN, 'name=~"^.*Run$"' )
	assert match( RULE_PATTERN, 'name!~"^.*Run$"' )

	assert match( RULE_PATTERN, 'type:run,hike,walk' )

# def test_rule_resource_pattern():
# 	assert match( RESOURCE_PATTERN, 'polar:1000#1' )
# 	assert match( RESOURCE_PATTERN, 'polar:1000#gpx' )
# 	# assert match( RESOURCE_PATTERN, 'polar:1000?1001.gpx' )
# 	assert match( RESOURCE_PATTERN, 'polar:1001#application/xml+gpx' )
# 	assert match( RESOURCE_PATTERN, 'polar:1001#application/xml+gpx-polar' )

def test_normalize( rule_parser ):
	p = rule_parser

	# numbers from 2000 to current year are treated as years, otherwise
	current_year = datetime.now().year
	assert p.normalize( '1000' ) == 'id == 1000'
	assert p.normalize( '1999' ) == 'id == 1999'
	assert p.normalize( '2000' ) == 'year == 2000'
	assert p.normalize( str( current_year ) ) == f'year == {current_year}'
	assert p.normalize( str( current_year + 1 ) ) == f'id == {current_year + 1}'

	# integer ranges can contain missing bounds and are treated as ids, bounds are inclusive
	assert p.normalize( '1000..1003' ) == 'id >= 1000 and id <= 1003'
	assert p.normalize( '1000..' ) == 'id >= 1000'
	assert p.normalize( '..1003' ) == 'id <= 1003'

	# integer lists are treated as id lists
	assert p.normalize( '100,101,102' ) == 'id in [100,101,102]'

	# there should be keywords for each registered service (and others)
	assert 'polar' in p.keywords
	assert p.normalize( 'polar' ) == f'"polar" in classifiers'
	# unknown keywords result in an error
	with raises( RuleSyntaxError ):
		p.normalize( 'unknown_keyword' )

	# todo: more tests with the normal rule engine syntax need to go in here
	# single equal is allowed and will be expanded to double
	assert p.normalize( 'id=1000' ) == 'id == 1000'

	# normal expressions are just passed through
	assert p.normalize( 'id!=1000' ) == 'id != 1000'

	# colon expressions
	assert p.normalize( 'id:' ) == 'id == null' # missing values is treated as null
	assert p.normalize( 'id:1000' ) == 'id == 1000' # normal case: expand to equals
	assert p.normalize( 'flag:true' ) == 'flag == true' and p.normalize( 'flag:false' ) == 'flag == false' # boolean flags
	assert p.normalize( 'name:"afternoon run"' ) == 'name != null and "afternoon run" in name.as_lower' # allow search-like string values
	assert p.normalize( 'name:afternoon' ) == 'name != null and "afternoon" in name.as_lower' # same for unquoted strings

	# custom normalizer handling
	assert p.normalize( 'type:run' ) == 'type.name == "run"'

	# date + time normalizing
	assert p.normalize( 'date:2020' ) == 'starttime_local >= d"2020-01-01T00:00:00+00:00" and starttime_local <= d"2020-12-31T23:59:59.999999+00:00"'
	assert p.normalize( 'date:2020-05' ) == 'starttime_local >= d"2020-05-01T00:00:00+00:00" and starttime_local <= d"2020-05-31T23:59:59.999999+00:00"'
	assert p.normalize( 'date:2020-05-13' ) == 'starttime_local >= d"2020-05-13T00:00:00+00:00" and starttime_local <= d"2020-05-13T23:59:59.999999+00:00"'

	assert p.normalize( 'time:10' ) == '__time__ >= d"0001-01-01T10:00:00+00:00" and __time__ <= d"0001-01-01T10:59:59.999999+00:00"'
	assert p.normalize( 'time:10:30' ) == '__time__ >= d"0001-01-01T10:30:00+00:00" and __time__ <= d"0001-01-01T10:30:59.999999+00:00"'
	assert p.normalize( 'time:10:30:50' ) == '__time__ >= d"0001-01-01T10:30:50+00:00" and __time__ <= d"0001-01-01T10:30:50.999999+00:00"'

def test_parse( rule_parser ):
	p = rule_parser

	assert (r := p.parse_rule( 'id=1000' ))
	assert r.evaluate( Activity( id=1000 ) )

	assert (r := p.parse_rule( 'id!=1000' ))
	assert r.evaluate( Activity( id=1001 ) )

	with raises( EvaluationError ):
		assert (r := p.parse_rule( 'id=~1000' )) # wrong operator, parsing fails
		r.evaluate( Activity( id=1000 ) )

	assert (r := p.parse_rule( 'unknown:1000' )) # parsing unknown fields is ok
	with raises( SymbolResolutionError ):
		assert r.evaluate( Activity( id=1000 ) ) # evaluating is not ok -> error

def test_evaluate( rule_parser ):
	p = rule_parser

	al = [
		Activity(
			id = 1000,
			name = 'Berlin',
		),
		Activity(
			id = 1001,
		)
	]

	assert p.parse_rule( 'id=1000' ).evaluate( A1 )
	assert p.parse_rule( f'year=2023' ).evaluate( A1 )
	assert p.parse_rule( 'classifier:polar' ).evaluate( A1 )
	assert p.parse_rule( 'lastyear' ).evaluate( A1 )

	assert p.parse_rule( 'name=Berlin' ).evaluate( A1 )
	assert not p.parse_rule( 'name=berlin' ).evaluate( A1 )

	assert p.parse_rule( 'description="Morning Run in Berlin"' ).evaluate( A1 )
	assert not p.parse_rule( 'description="morning run in berlin"' ).evaluate( A1 )

	assert p.parse_rule( 'name:berlin' ).evaluate( A1 )
	assert not p.parse_rule( 'name:hamburg' ).evaluate( A1 )
	assert p.parse_rule( 'description:"morning run"' ).evaluate( A1 )

	assert list( p.parse_rule( 'name:berlin' ).filter( al ) ) == [ al[0] ]
	assert not p.parse_rule( 'location_place:hamburg' ).evaluate( A1 )

	assert list( p.parse_rule( 'name:' ).filter( al ) ) == [ al[1] ]

	with raises( SymbolResolutionError ):
		p.parse_rule( 'invalid=1000' ).evaluate( A1 )

	# RuleSyntaxError should never happen ...

def test_evaluate_multipart( rule_parser ):
	p = rule_parser

	p1 = ActivityPart( uids=['polar:101' ], gap=time( 0, 0, 0 ) )
	p2 = ActivityPart( uids=['polar:102', 'strava:102' ], gap=time( 1, 0, 0 ) )
	a = Activity( parts=[ p1, p2 ] )

	assert a.multipart
	assert p.parse_rule( 'multipart=true' ).evaluate( a )
	assert not p.parse_rule( 'multipart=false' ).evaluate( a )
	assert p.parse_rule( 'multipart:true' ).evaluate( a )
	assert not p.parse_rule( 'multipart:false' ).evaluate( a )

def test_type( rule_parser ):
	p = rule_parser
	# assert parse_eval( 'type=run', A1 ) # todo: support this?
	assert p.parse_rule( 'type:run' ).evaluate( A1 )
	assert p.parse_rule( 'type:Run' ).evaluate( A1 )

def test_list( rule_parser ):
	p = rule_parser
	assert p.parse_rule( '1000,1001,1002' ).evaluate( A1 )
	assert not p.parse_rule( '100,101,102' ).evaluate( A1 )

def test_range( rule_parser ):
	p = rule_parser

	assert not p.parse_rule( 'id=999..1001' ).evaluate( A1 )
	assert p.parse_rule( 'id:999..1001' ).evaluate( A1 )
	assert p.parse_rule( 'id:999.0..1001' ).evaluate( A1 ) # mixed int/float works as well
	assert p.parse_rule( 'id:999..' ).evaluate( A1 )
	assert p.parse_rule( 'id:..1001' ).evaluate( A1 )

	assert not p.parse_rule( 'id:800..900' ).evaluate( A1 )
	assert not p.parse_rule( 'id:..900' ).evaluate( A1 )
	assert not p.parse_rule( 'id:1001..' ).evaluate( A1 )

	assert p.parse_rule( 'heartrate:100.0..200.0' ).evaluate( A1 )

def test_date_time( rule_parser ):
	p = rule_parser

	assert p.parse_rule( 'date:2023' ).evaluate( A1 )
	assert p.parse_rule( 'date:2023-01' ).evaluate( A1 )
	assert p.parse_rule( 'date:2023-01-13' ).evaluate( A1 )

	assert not p.parse_rule( 'date:2022' ).evaluate( A1 )
	assert not p.parse_rule( 'date:2022-01' ).evaluate( A1 )
	assert not p.parse_rule( 'date:2022-01-13' ).evaluate( A1 )

	#	assert p.parse_rule( 'date=2023-01-13' ).evaluate( A1 )

	assert p.parse_rule( 'date:2022..2023' ).evaluate( A1 )
	assert p.parse_rule( 'date:2022..' ).evaluate( A1 )
	assert p.parse_rule( 'date:..2023' ).evaluate( A1 )
	assert p.parse_rule( 'date:2023-01-12..2023-02' ).evaluate( A1 )

	# assert p.parse_rule( 'time=10:00:42' ).evaluate( A1 )
	assert p.parse_rule( 'time:10' ).evaluate( A1 )
	assert p.parse_rule( 'time:10:00' ).evaluate( A1 )
	assert p.parse_rule( 'time:10:00:42' ).evaluate( A1 )

	assert p.parse_rule( 'time:09..11' ).evaluate( A1 )
	assert p.parse_rule( 'time:09..' ).evaluate( A1 )
	assert p.parse_rule( 'time:..11' ).evaluate( A1 )
	assert p.parse_rule( 'time:09:00..11:00' ).evaluate( A1 )
	assert p.parse_rule( 'time:09:00:05..10:00:50' ).evaluate( A1 )

def test_parse_date_range():

	assert parse_date_range_as_str( '2022..2023' ) == ('2022-01-01T00:00:00+00:00', '2023-12-31T23:59:59.999999+00:00')
	assert parse_date_range_as_str( '2022..' ) == ('2022-01-01T00:00:00+00:00', '9999-12-31T00:00:00+00:00')
	assert parse_date_range_as_str( '..2023' ) == ('0001-01-01T00:00:00+00:00', '2023-12-31T23:59:59.999999+00:00')

	assert parse_date_range_as_str( '2022-03..2022-03' ) == ('2022-03-01T00:00:00+00:00', '2022-03-31T23:59:59.999999+00:00')
	assert parse_date_range_as_str( '..2022-03' ) == ('0001-01-01T00:00:00+00:00', '2022-03-31T23:59:59.999999+00:00')
	assert parse_date_range_as_str( '2022-03..' ) == ('2022-03-01T00:00:00+00:00', '9999-12-31T00:00:00+00:00')

	assert parse_date_range_as_str( '2022-03-15..2022-03-16' ) == ('2022-03-15T00:00:00+00:00', '2022-03-16T23:59:59.999999+00:00')
	assert parse_date_range_as_str( '..2022-03-16' ) == ('0001-01-01T00:00:00+00:00', '2022-03-16T23:59:59.999999+00:00')
	assert parse_date_range_as_str( '2022-03-15..' ) == ('2022-03-15T00:00:00+00:00', '9999-12-31T00:00:00+00:00')
