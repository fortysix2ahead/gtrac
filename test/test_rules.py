from datetime import datetime
from re import match
from typing import cast

from pytest import raises
from rule_engine import Context
from rule_engine import resolve_attribute
from rule_engine import Rule
from rule_engine import RuleSyntaxError
from rule_engine import SymbolResolutionError

from tracs.activity import Activity
from tracs.rules_parser import INT_LIST_PATTERN
from tracs.rules_parser import INT_PATTERN
from tracs.rules_parser import INT_RANGE_PATTERN
from tracs.rules_parser import KEYWORD_PATTERN
from tracs.rules_parser import normalize
from tracs.rules_parser import parse_rule
from tracs.rules_parser import RULE_PATTERN

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

	assert match( INT_RANGE_PATTERN, '1000..1002' )
	assert match( INT_RANGE_PATTERN, '1000..' )
	assert match( INT_RANGE_PATTERN, '..1002' )

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
	a = Activity(
		id = 1000,
		time = datetime.utcnow(),
		uids = ['polar:123456', 'strava:123456']
	)

	assert parse_rule( 'id=1000' ).evaluate( a )
	assert parse_rule( f'year={datetime.utcnow().year}' ).evaluate( a )
	assert parse_rule( 'classifier:polar' ).evaluate( a )

	with raises( SymbolResolutionError ):
		parse_rule( 'invalid=1000' ).evaluate( a )

	# RuleSyntaxError should never happen ...
