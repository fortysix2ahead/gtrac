from json import loads

from pydantic import ValidationError
from pytest import mark, fail
from stravalib.client import Client
from stravalib.model import DetailedActivity

from conftest import service
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
	json_str = detailed_activity.model_dump_json( exclude_unset=True, exclude_defaults=True, exclude_none=True, indent=2 )
	print( json_str )

	# load json from string and parse it into a detailed activity again, this fails with:
	# start_date_local
	#   Input should have timezone info [type=timezone_aware, input_value='2022-10-16T14:23:40', input_type=str]
	#     For further information visit https://errors.pydantic.dev/2.9/v/timezone_aware
	try:
		DetailedActivity.model_validate_json( loads( json_str ) )
	except ValidationError:
		fail( 'unable to transform json to detailed activity' )
