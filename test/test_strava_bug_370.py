from json import loads

from pydantic import ValidationError
from pytest import mark, fail, raises
from stravalib.client import Client
from stravalib.model import DetailedActivity

from test.conftest import service
from tracs.plugins.strava import Strava


# test case with development account

@mark.context( env='live', persist='clone', cleanup=False )
@mark.service( cls=Strava, init=True, register=True )
def test_activity( service ):
	client_id = service.config_value( 'client_id' )
	client_secret = service.config_value( 'client_secret' )
	access_token = service.state_value( 'access_token' )
	refresh_token = service.state_value( 'refresh_token' )

	client = Client( access_token=access_token )
	client.refresh_access_token( client_id=client_id, client_secret=client_secret, refresh_token=refresh_token )

	# load detailed activity and dump it into a string
	detailed_activity = client.get_activity( 7973155107, include_all_efforts=True )
	assert detailed_activity.start_date.tzinfo is not None
	assert detailed_activity.start_date_local.tzinfo is None
	json_str = detailed_activity.model_dump_json( exclude_unset=True, exclude_defaults=True, exclude_none=True, indent=2 )

	print( json_str )

	# this works ...
	try:
		DetailedActivity.model_validate_json( json_str )
	except ValidationError:
		fail( 'unable to transform json to detailed activity' )

	# this does not work: after loading the json the field "start_date" is of type str, not datetime, this creates a failure when loading
	with raises( ValidationError ):
		json = loads( json_str )
		DetailedActivity.model_validate_json( json )
