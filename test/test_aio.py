
from pytest import mark

from tracs.aio import import_activities

@mark.context( env='empty', persist='clone', cleanup=True )
@mark.file( 'environments/default/takeouts' )
def test_import( path, env ):
	drivey_file = f'{str( path )}/drive-20240825-160655.gpx'
	activities = import_activities( env.ctx, [], location=drivey_file )
	assert [ a.id for a in activities ] == [1]

	drivey_zip = f'{str( path )}/drive-20240826-132945.zip'
	activities = import_activities( env.ctx, [], location=drivey_zip )
	assert [ a.id for a in activities ] == [2]

	drivey_gzip = f'{str( path )}/drive-20240825-161341.gpx.gz'
	activities = import_activities( env.ctx, [], location=drivey_gzip )
	assert [ a.id for a in activities ] == [3]

	drivey_folder = f'{str( path )}/drivey'
	activities = import_activities( env.ctx, [], location=drivey_folder )
	assert [ a.id for a in activities ] == [ i for i in range( 4, 14 ) ]

@mark.context( env='default', persist='clone', cleanup=True )
def test_reimport( env ):
	activities = env.db.activities
