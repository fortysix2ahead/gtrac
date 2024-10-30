
from __future__ import annotations

from logging import getLogger

from pytest import mark

from tracs.plugins.local import Local
from tracs.utils import fspath

log = getLogger( __name__ )

# noinspection PyUnresolvedReferences
@mark.context( env='default', persist='clone', cleanup=True )
@mark.service( cls=Local, init=True, register=True )
def test_import( service ):
	# import from single file
	src_fs, src_path = fspath( service.ctx.config_fs.getsyspath( 'takeouts/drive-20240825-160655.gpx' ) )
	activities = service.import_activities( fs=src_fs, path=src_path, classifier='drivey' )
	assert [ a.uid.to_str() for a in activities ] == ['drivey:240825140655']

	# import from single gzip file
	src_fs, src_path = fspath( service.ctx.config_fs.getsyspath( 'takeouts/drive-20240825-161341.gpx.gz' ) )
	activities = service.import_activities( fs=src_fs, path=src_path, classifier='drivey' )
	assert [ a.uid.to_str() for a in activities ] == ['drivey:240825141340']

	# import from single zip file
	src_fs, src_path = fspath( service.ctx.config_fs.getsyspath( 'takeouts/drive-20240826-132945.zip' ) )
	activities = service.import_activities( fs=src_fs, path=src_path, classifier='drivey' )
	assert [ a.uid.to_str() for a in activities ] == ['drivey:240826112945']

	# import from dir
	src_fs, src_path = fspath( service.ctx.config_fs.getsyspath( 'takeouts/drivey' ) )
	activities = service.import_activities( fs=src_fs, path=src_path, classifier='drivey' )
	assert len( activities ) == 10

	# import from zip
	src_fs, src_path = fspath( service.ctx.config_fs.getsyspath( 'takeouts/drivey.zip' ) )
	activities = service.import_activities( fs=src_fs, path=src_path, classifier='drivey' )
	assert len( activities ) == 0 # all skipped

	#
	src_fs, src_path = fspath( service.ctx.config_fs.getsyspath( 'takeouts/drivey' ) )
	activities = service.import_activities( fs=src_fs, path='no_existing_path', classifier='drivey' )
	assert len( activities ) == 0

	assert sorted( service.dbfs.listdir( 'drivey/24/08' ) ) == ['25', '26', '27', '28']
	assert sorted( service.dbfs.listdir( 'drivey/24/08/27/240827145524' ) ) == [ '240827145524.gpx' ]
	# assert all( [ f.endswith( '.gpx' ) for f in service.dbfs.walk.files() ] )

