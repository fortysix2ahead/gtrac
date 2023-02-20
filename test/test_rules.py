from dataclass_factory import Factory, Schema
from rich.console import Console
from rule_engine import Rule
from tracs.activity import Activity
from tracs.resources import Resource


def test_rule_engine():
    rule = Rule( 'heartrate == 180' )
    a = Activity()
    a.heartrate = 180
    print( rule.matches( a ) )


    c = Console()
    r = Resource( type='json', path='1234.json', uid='polar:1234' )

    rs = Schema( exclude=[ 'raw', 'content', 'text', 'resources' ], omit_default=True )
    f = Factory( schemas={ Resource: rs }, debug_path=True )

    c.print( f.dump( r, Resource ) )

