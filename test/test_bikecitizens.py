
from pytest import mark

from tracs.plugins.bikecitizens import Bikecitizens
from tracs.plugins.bikecitizens import BASE_URL
from tracs.plugins.bikecitizens import API_URL
from tracs.service import Service

from .helpers import skip_live

@mark.context( env='live', persist='clone', cleanup=True )
@mark.service( cls=Bikecitizens )
def test_service_creation( service: Bikecitizens ):
	assert type( service ) is Bikecitizens

	assert service.api_url == f'{API_URL}'
	assert service.base_url == f'{BASE_URL}'
	assert service.signin_url == f'{BASE_URL}/users/sign_in'
	assert service.user_url == f'{API_URL}/api/v1/users/None'

	assert service.base_url == BASE_URL
	# assert service.base_path is not None and service.overlay_path is not None

@skip_live
@mark.context( env='live', persist='clone', cleanup=False )
@mark.service( cls=Bikecitizens, init=True, register=True )
def test_import( service: Service ):
	activities = service.import_activities()
	assert [ a.uid.to_str() for a in activities ] == ['bikecitizens:8201734', 'bikecitizens:8201735']
