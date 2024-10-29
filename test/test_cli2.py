from logging import getLogger

from pytest import mark

from helpers import invoke_cli as invoke
from tracs.config import ApplicationContext as Context

log = getLogger( __name__ )

cmd_import_bikecitizens = 'import bikecitizens'

# local imports
cmd_import_local = 'import local' # this does nothing
cmd_import_file_or_dir = 'import --from {}'
cmd_import_local_file_or_dir = 'import --from {} local' # same as above, local shall be implicit when --from is used and service arg is missing

# strava imports
cmd_import_strava = 'import strava' # import from strava service (remote)
cmd_import_strava_from = 'import --from strava' # look into default strava takeout location
cmd_import_strava_takeout_from = 'import --from {} strava' # look into arbitrary strava takeout location, should work, can be a zip or a dir

# combined imports
cmd_import_local_strava_from = 'import --from {} local strava' # --from implies local, should at least give a warning

cmd_list = 'list'
cmd_list_1 = 'list 1'
cmd_list_l_1 = 'list -l "id name" 1'
cmd_list_1_tags = 'list -l "id tags" 1'

cmd_tag = 'tag -t one 1'

cmd_version = 'version'

# no command

@mark.context( env='default', persist='clone', cleanup=True )
def test_nocommand( ctx: Context ):
	i = invoke( ctx, '' )
	assert i.out == ''
	assert i.err.contains_all( 'Usage', 'Error: Missing command' )

# list

@mark.xfail # todo: needs improvement
@mark.context( env='default', persist='clone', cleanup=True )
def test_list( ctx: Context ):
	i = invoke( ctx, cmd_list )
	assert i.out.contains( 'Run at Noon' )
	# todo: don't know how to extend the width of the virtual terminal to more than 80 characters
	assert i.out.table_header == [ 'id', 'name', 'type', 'starttime_l…', 'uid', 'uids' ]
	i = invoke( ctx, cmd_list_1 )
	assert i.out.table_header == [ 'id', 'name', 'type', 'starttime_lo…', 'uid', 'uids' ]

	i = invoke( ctx, cmd_list_l_1 )
	assert i.out.table_header == [ 'id', 'name' ]

# import
@mark.context( env='empty', persist='clone', cleanup=True, json=True )
@mark.file( 'environments/default/takeouts' )
def test_import( ctx: Context, path ):
	# import single file
	drivey_file = f'{str( path )}/drive-20240825-160655.gpx'
	cmd = cmd_import_file_or_dir.format( drivey_file )
	json = invoke( ctx, cmd ).json
	assert [ a['id'] for a in json ] == [1]

	drivey_zip = f'{str( path )}/drive-20240826-132945.zip'
	cmd = cmd_import_file_or_dir.format( drivey_zip )
	json = invoke( ctx, cmd ).json
	assert [ a['id'] for a in json ] == [2]

	drivey_folder = f'{str( path )}/drivey'

# tagging

@mark.xfail # todo: needs improvement
@mark.context( env='default', persist='clone', cleanup=True )
def test_tagging( ctx: Context ):
	# no output -> no assert
	i = invoke( ctx, cmd_tag, print_stdout=True )

	# check tag in list view
	i = invoke( ctx, cmd_list_1_tags, print_stdout=True )
	assert i.out.table_header == [ 'id', 'tags' ]
	assert i.out.table_row( 0 ) == [ '1', 'one' ]

# version

@mark.context( env='default', persist='clone', cleanup=True )
def test_version( ctx: Context ):
	assert invoke( ctx, cmd_version ).out == '0.1.0'

@mark.context( env='default', persist='clone', cleanup=True, json=True )
def test_version_json( ctx: Context ):
	assert invoke( ctx, cmd_version ).json == { 'version': '0.1.0' }
