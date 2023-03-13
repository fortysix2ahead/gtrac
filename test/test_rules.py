
from datetime import datetime
from re import match
from typing import cast

from dateutil.tz import UTC
from pytest import raises
from rich.pretty import pprint
from rule_engine import Context
from rule_engine import resolve_attribute
from rule_engine import Rule
from rule_engine import SymbolResolutionError

from tracs.activity import Activity
from tracs.activity_types import ActivityTypes
from tracs.rules_parser import DATE_PATTERN
from tracs.rules_parser import FUZZY_DATE_PATTERN
from tracs.rules_parser import INT_LIST_PATTERN
from tracs.rules_parser import INT_PATTERN
from tracs.rules_parser import KEYWORD_PATTERN
from tracs.rules_parser import normalize
from tracs.rules_parser import parse_date_range_as_str
from tracs.rules_parser import parse_rule
from tracs.rules_parser import RANGE_PATTERN
from tracs.rules_parser import RESOLVERS
from tracs.rules_parser import RULE_PATTERN
from tracs.rules_parser import TIME_PATTERN

NOW = datetime.utcnow()

A1 = Activity(
	id=1000,
	name="Berlin",
	description="Morning Run in Berlin",
	type=ActivityTypes.run,
	time=datetime( 2023, 1, 13, 10, 0, 42, tzinfo=UTC ),
	heartrate=160,
	uids=['polar:123456', 'strava:123456']
)

def test_rule_engine():
	rule = Rule( 'heartrate == 180' )
	a = Activity( heartrate=180, time=datetime.utcnow(), tags=['morning', 'salomon', 'tired'], uids=['polar:1234', 'strava:3456'] )
	assert rule.matches( a )

	rule = Rule( 'heartrate_max == 180' )
	assert not rule.matches( a )

	# how to get around a SymbolResolutionError:
	context = Context( default_value=None )
	rule = Rule( 'year == 2023', context=context )
	assert not rule.matches( a )

	# how to use a custom resolver
	def resolve_year( thing, name ):
		if name == 'year':
			return cast( Activity, thing ).time.year
		elif name == 'classifiers' and type( thing ) is tuple:
			return list( map( lambda s: s.split( ':', 1 )[0], thing ) )
		else:
			return resolve_attribute( thing, name )

	context = Context( default_value=None, resolver=resolve_year )
	assert Rule( 'heartrate == 180', context=context ).matches( a )
	assert Rule( 'year == 2023', context=context ).matches( a )
	assert Rule( 'heartrate == 180 and year == 2023', context=context ).matches( a )
	assert not Rule( 'heartrate == 170 and year == 2023', context=context ).matches( a )

	assert Rule( '"tired" in tags', context=context ).matches( a )
	assert not Rule( '"evening" in tags', context=context ).matches( a )

	assert Rule( '"polar:1234" in uids', context=context ).matches( a )
	assert not Rule( '"polar" in uids', context=context ).matches( a )
	assert Rule( '"polar" in uids.classifiers', context=context ).matches( a )

def test_rule_pattern():
	# special cases
	# numbers shall be treated as ids
	assert match( INT_PATTERN, '1000' )
	assert match( INT_LIST_PATTERN, '1000,1001,1002' )
	assert not match( INT_LIST_PATTERN, '1000,1001,1002,' )

	assert match( RANGE_PATTERN, '1000..1002' )
	assert match( RANGE_PATTERN, '1000..' )
	assert match( RANGE_PATTERN, '..1002' )
	assert match( RANGE_PATTERN, '100.4..100.9' )
	assert match( RANGE_PATTERN, '2020-01-01..2020-06-30' )
	assert match( RANGE_PATTERN, '10:00:00..11:00:00' )

	assert not match( DATE_PATTERN, '2022' )
	assert not match( DATE_PATTERN, '2022-03' )
	assert match( DATE_PATTERN, '2022-03-13' )
	assert match( FUZZY_DATE_PATTERN, '2022' )
	assert match( FUZZY_DATE_PATTERN, '2022-03' )
	assert match( FUZZY_DATE_PATTERN, '2022-03-13' )

	assert not match( TIME_PATTERN, '13' )
	assert not match( TIME_PATTERN, '13:10' )
	assert match( TIME_PATTERN, '13:10:42' )

	# keywords, must begin with a letter and may contain letters, numbers, dash und underscores

	assert match( KEYWORD_PATTERN, 'polar' )
	assert match( KEYWORD_PATTERN, 'polar_2022' )
	assert match( KEYWORD_PATTERN, 'polar-2022' )
	assert match( KEYWORD_PATTERN, 'Polar22' )
	assert not match( KEYWORD_PATTERN, '1Polar22' )

	# normal expressions

	assert match( RULE_PATTERN, 'id:1000' )
	assert match( RULE_PATTERN, 'ID:1000' )

	assert match( RULE_PATTERN, 'id=1000' )
	assert match( RULE_PATTERN, 'id==1000' )
	assert match( RULE_PATTERN, 'id!=1000' )
	assert match( RULE_PATTERN, 'id>1000' )
	assert match( RULE_PATTERN, 'id>=1000' )
	assert match( RULE_PATTERN, 'id<1000' )
	assert match( RULE_PATTERN, 'id<=1000' )

	assert match( RULE_PATTERN, 'name=Berlin' )
	assert match( RULE_PATTERN, 'name="Morning Run"' )
	assert match( RULE_PATTERN, 'name!="Morning Run"' )
	assert match( RULE_PATTERN, 'name=~"^.*Run$"' )
	assert match( RULE_PATTERN, 'name!~"^.*Run$"' )

def test_normalize():
	assert normalize( '1000' ) == 'id == 1000'
	assert normalize( 'id:1000' ) == 'id == 1000'
	assert normalize( 'id=1000' ) == 'id == 1000'

def test_parse():
	with raises( RuntimeError ):
		assert (r := parse_rule( 'unknown:1000' ))

	with raises( RuntimeError ):
		assert (r := parse_rule( 'id=~1000' ))

	assert (r := parse_rule( 'id=1000' ))

	# test against activity
	assert r.evaluate( Activity( id=1000 ) )
	assert Rule( 'unknown == 1000' ).evaluate( Activity( id=1000 ) )

def test_evaluate():
	al = [
		Activity(
			id = 1000,
			name = 'Berlin',
		),
		Activity(
			id = 1001,
		)
	]

	assert parse_rule( 'id=1000' ).evaluate( A1 )
	assert parse_rule( f'year={NOW.year}' ).evaluate( A1 )
	assert parse_rule( 'classifier:polar' ).evaluate( A1 )
	assert parse_rule( 'thisyear' ).evaluate( A1 )

	assert parse_rule( 'name=Berlin' ).evaluate( A1 )
	assert not parse_rule( 'name=berlin' ).evaluate( A1 )

	assert parse_rule( 'description="Morning Run in Berlin"' ).evaluate( A1 )
	assert not parse_rule( 'description="morning run in berlin"' ).evaluate( A1 )

	assert parse_rule( 'name:berlin' ).evaluate( A1 )
	assert not parse_rule( 'name:hamburg' ).evaluate( A1 )
	assert parse_rule( 'description:"morning run"' ).evaluate( A1 )

	assert list( parse_rule( 'name:berlin' ).filter( al ) ) == [ al[0] ]
	assert not parse_rule( 'location_place:hamburg' ).evaluate( A1 )

	with raises( SymbolResolutionError ):
		parse_rule( 'invalid=1000' ).evaluate( A1 )

	# RuleSyntaxError should never happen ...

def test_type():
	assert parse_eval( 'type=run', A1 )
	assert parse_eval( 'type:run', A1 )

def test_range():
	assert not parse_eval( 'id=999..1001', A1 )
	assert parse_eval( 'id:999..1001', A1 )
	assert parse_eval( 'id:999.0..1001', A1 ) # mixed int/float works as well
	assert parse_eval( 'id:999..', A1 )
	assert parse_eval( 'id:..1001', A1 )
	assert not parse_eval( 'id:800..900', A1 )
	assert not parse_eval( 'id:..900', A1 )
	assert not parse_eval( 'id:1001..', A1 )

	assert parse_eval( 'heartrate:100.0..200.0', A1 )

def test_date_time():
	from arrow import arrow
	from dateutil.parser import parse

	assert parse_eval( 'date=2023-01-13', A1 )
	assert parse_eval( 'date:2023', A1 )
	assert not parse_eval( 'date:2022', A1 )
	assert parse_eval( 'date:2023-01', A1 )
	assert not parse_eval( 'date:2022-01', A1 )
	assert parse_eval( 'date:2023-01-13', A1 )
	assert not parse_eval( 'date:2022-01-13', A1 )

	assert parse_eval( 'date:2022..2023', A1 )
	assert parse_eval( 'date:2022..', A1 )
	assert parse_eval( 'date:..2023', A1 )
	assert parse_eval( 'date:2023-01-12..2023-02', A1 )

	# assert parse_eval( 'time=10:00:42', A1 )

def test_parse_date_range():

	assert parse_date_range_as_str( '2022..2023' ) == ('2022-01-01', '2023-12-31')
	assert parse_date_range_as_str( '2022..' ) == ('2022-01-01', '9999-12-31')
	assert parse_date_range_as_str( '..2023' ) == ('0001-01-01', '2023-12-31')

	assert parse_date_range_as_str( '2022-03..2022-03' ) == ('2022-03-01', '2022-03-31')
	assert parse_date_range_as_str( '..2022-03' ) == ('0001-01-01', '2022-03-31')
	assert parse_date_range_as_str( '2022-03..' ) == ('2022-03-01', '9999-12-31')

	assert parse_date_range_as_str( '2022-03-15..2022-03-16' ) == ('2022-03-15', '2022-03-16')
	assert parse_date_range_as_str( '..2022-03-16' ) == ('0001-01-01', '2022-03-16')
	assert parse_date_range_as_str( '2022-03-15..' ) == ('2022-03-15', '9999-12-31')

# helper

def parse_eval( rule: str, thing: Activity ) -> bool:
	return parse_rule( rule ).evaluate( thing )

def test_resolvers():
	for key, val in RESOLVERS.items():
		pprint( f'{key}: {val( A1, key )}' )
