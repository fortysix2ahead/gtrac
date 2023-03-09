
from re import match

from dataclass_factory import Factory
from dataclass_factory import Schema
from rich.console import Console
from rule_engine import Rule

from pytest import raises

from tracs.activity import Activity
from tracs.resources import Resource
from tracs.rules_parser import RULE_PATTERN
from tracs.rules_parser import INT_LIST_PATTERN
from tracs.rules_parser import INT_PATTERN
from tracs.rules_parser import INT_RANGE_PATTERN
from tracs.rules_parser import KEYWORD_PATTERN
from tracs.rules_parser import normalize
from tracs.rules_parser import parse_rule

def test_rule_engine():
	rule = Rule( 'heartrate == 180' )
	a = Activity()
	a.heartrate = 180
	print( rule.matches( a ) )

	c = Console()
	r = Resource( type='json', path='1234.json', uid='polar:1234' )

	rs = Schema( exclude=['raw', 'content', 'text', 'resources'], omit_default=True )
	f = Factory( schemas={ Resource: rs }, debug_path=True )

	c.print( f.dump( r, Resource ) )

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

	assert normalize( '1000' ) == 'id==1000'
	assert normalize( 'id:1000' ) == 'id==1000'
	assert normalize( 'id=1000' ) == 'id==1000'

def test_parse():

	with raises( RuntimeError ):
		assert (r := parse_rule( 'unknown:1000' ))

	with raises( RuntimeError ):
		assert (r := parse_rule( 'id=~1000' ))

	assert (r := parse_rule( 'id=1000' ))

	# test against activity
	assert r.evaluate( Activity( id=1000 ) )
