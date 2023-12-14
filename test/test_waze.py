from pathlib import Path
from typing import cast

from gpxpy.gpx import GPX

from pytest import mark

from tracs.plugins.waze import AccountActivity, Waze, WAZE_ACCOUNT_ACTIVITY_TYPE, WAZE_ACCOUNT_INFO_TYPE, WAZE_TYPE, WazeAccountActivityImporter, WazeImporter

@mark.file( 'environments/default/takeouts/waze/2020-09/account_activity_3.csv' )
def test_read_account_activity_2020( path ):
	resource = WazeAccountActivityImporter().load( path=path )
	location_details = cast( AccountActivity, resource.data ).location_details
	assert len( location_details ) == 1
	assert len( location_details[0].as_point_list() ) == 25

@mark.file( 'environments/default/takeouts/waze/2022-01/account_activity_3.csv' )
def test_read_account_activity_2022( path ):
	resource = WazeAccountActivityImporter().load( path=path )
	location_details = cast( AccountActivity, resource.data ).location_details
	assert len( location_details ) == 2
	assert len( location_details[0].as_point_list() ) == 310
	assert len( location_details[1].as_point_list() ) == 316

@mark.file( 'environments/default/takeouts/waze/2023-04/account_activity_3.csv' )
def test_read_account_activity_2023( path ):
	resource = WazeAccountActivityImporter().load( path=path )
	location_details = cast( AccountActivity, resource.data ).location_details
	assert len( location_details ) == 2
	assert len( location_details[0].as_point_list() ) == 146
	assert len( location_details[1].as_point_list() ) == 71

# dummy test case: can read, but data is not used anywhere
@mark.file( 'environments/default/takeouts/waze/2023-04/account_activity_3.csv' )
def test_read_account_info( path ):
	resource = WazeAccountActivityImporter().load( path=path )

@mark.file( 'environments/default/db/waze/20/07/12/200712074743/200712074743.txt' )
def test_activity_from_raw( path ):
	resource = WazeImporter().load( path )
	assert len( resource.data.points ) == 137

@mark.service( cls=Waze )
def test_path_for( service ):
	assert service.path_for_id( '231201102030' ) == Path( '23/12/01/231201102030' )
	assert service.path_for_id( '1' ) == Path( '00/00/01/000001' )
	assert service.path_for_id( '231201102030', 'waze' ) == Path( 'waze/23/12/01/231201102030' )
	assert service.path_for_id( '231201102030', resource_path='recording.gpx' ) == Path( '23/12/01/231201102030/recording.gpx' )
	assert service.path_for_id( '231201102030', base_path='waze', resource_path='recording.gpx' ) == Path( 'waze/23/12/01/231201102030/recording.gpx' )
	assert service.path_for_id( '231201102030', base_path='waze', resource_path='recording.gpx', as_path=False ) == 'waze/23/12/01/231201102030/recording.gpx'

@mark.context( env='default', persist='clone', cleanup=True )
@mark.service( cls=Waze, init=True, register=True )
def test_fetch_from_takeouts( service ):
	# this does not do anything because from_takeouts is not set
	resources = service.fetch( force=False, pretend=False )
	assert len( resources ) == 0

	# set takeouts flat
	resources = service.fetch( force=False, pretend=False, from_takeouts=True )
	assert len( resources ) == 4

	for r in resources:
		gpx = service.download( r, force=False, pretend=False )
		assert len( gpx ) == 1 and isinstance( gpx[0].raw, GPX )
