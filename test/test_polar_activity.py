
from datetime import datetime
from datetime import time
from datetime import timezone

from dataclass_factory import Factory
from dateutil.tz import tzlocal

from pytest import mark

from tracs.plugins.polar import PolarActivity, PolarFlowExercise
from tracs.activity_types import ActivityTypes

@mark.file( 'libraries/default/polar/1/0/0/100001/100001.raw.json' )
def test_exercise( json ):
	pfe = Factory().load(json, PolarFlowExercise)
	assert pfe.local_id == 100001
	assert pfe.title == '00:25:34;0.0 km'
	assert pfe.type == 'EXERCISE'
	assert pfe.distance == 12000.3
	assert pfe.calories == 456

	pa = pfe.as_activity()
	assert pa.type == ActivityTypes.run
	assert pa.time == datetime(2011, 4, 28, 15, 48, 10, tzinfo=timezone.utc)
	assert pa.localtime == datetime(2011, 4, 28, 17, 48, 10, tzinfo=tzlocal())
	assert pa.duration == time(0, 25, 35)

@mark.file( 'libraries/default/polar/1/0/0/100012/100012.raw.json' )
def test_fitnessdata( json ):
	pa = Factory().load( json, PolarFlowExercise )
	assert pa.local_id == 100012
	assert pa.index == 46

@mark.file( 'libraries/default/polar/1/0/0/100013/100013.raw.json' )
def test_orthostatic( json ):
	pa = PolarActivity( raw=json )
	assert pa.raw_id == 100013

@mark.file( 'libraries/default/polar/1/0/0/100014/100014.raw.json' )
def test_rrrecording( json ):
	pa = PolarActivity( raw=json )
	assert pa.raw_id == 100014
