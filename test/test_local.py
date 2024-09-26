
from __future__ import annotations

from io import UnsupportedOperation
from logging import getLogger

from pytest import mark, raises

from tracs.plugins.local import Local

log = getLogger( __name__ )

@mark.context( env='default', persist='clone', cleanup=True )
@mark.service( cls=Local, init=True, register=True )
def test_unified_import_from_zip( service ):
	location = service.ctx.config_fs.getsyspath( 'takeouts/drivey.zip' )
	activities, fs = service.unified_import( service.ctx, classifier='drivey', location=location )
	assert len( activities ) == 13
	assert all( [ a.uid.classifier == 'drivey' for a in activities ] )
	assert all( [ len( a.resources ) == 1 for a in activities ] )

	assert sorted( fs.listdir( 'drivey/24/08' ) ) == ['25', '26', '27', '28']
	assert sorted( fs.listdir( 'drivey/24/08/27/240827145524' ) ) == [ '240827145524.gpx' ]
	assert all( [ f.endswith( '.gpx' ) for f in fs.walk.files() ] )

@mark.context( env='default', persist='clone', cleanup=True )
@mark.service( cls=Local, init=True, register=True )
def test_unified_import_from_dir( service ):
	location = service.ctx.config_fs.getsyspath( 'takeouts/drivey' )
	activities, fs = service.unified_import( service.ctx, classifier='drivey', location=location )
	assert len( activities ) == 13
	assert all( [ f.endswith( '.gpx' ) for f in fs.walk.files() ] )

@mark.context( env='default', persist='clone', cleanup=True )
@mark.service( cls=Local, init=True, register=True )
def test_unified_import_fail( service ):
	with raises( UnsupportedOperation ):
		activities, fs = service.unified_import( service.ctx, classifier='drivey', location='something_that_does_not_exist' )

	# todo: this should be allowed
	location = service.ctx.config_fs.getsyspath( 'takeouts/drivey/drive-20240825-160655.gpx' )
	with raises( UnsupportedOperation ):
		activities, fs = service.unified_import( service.ctx, classifier='drivey', location=location )
