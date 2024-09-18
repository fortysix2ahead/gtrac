from logging import getLogger
from re import compile
from typing import List

from attrs import define
from fs.base import FS
from more_itertools.recipes import first_true

from plugins.json import JSONHandler
from tracs.resources import Resource
from tracs.uid import UID

log = getLogger( __name__ )

ACCOUNT_DATA = compile( r'account-data-\d+\.json' )
ACCOUNT_PROFILE = compile( r'account-profile-\d+\.json' )
TRAINING_SESSION = compile( r'training-session-\d{4}-\d{2}-\d{2}-(\d+)(-\w{8}-\w{4}-\w{4}-\w{4}-\w{12})?\.json' )

@define
class PolarTrainingSession:

	pass

class PolarTrainingSessionHandler( JSONHandler ):

	pass


class PolarFlowTakeoutImporter:

	json_handler = JSONHandler()

	def fetch( self, fs: FS, existing_uids: List[UID], force: bool = False ) -> List[Resource]:
		ids = [uid.local_id for uid in existing_uids]
		files = list( fs.walk.files( '' ) )

		data = first_true( files, pred=lambda f: ACCOUNT_DATA.fullmatch( f ) )
		profile = first_true( files, pred=lambda f: ACCOUNT_PROFILE.fullmatch( f ) )
		if not data and not profile:
			log.error( f'unable to find Polar takeout data in {fs}' )
			return []

		for f in files:
			if m := TRAINING_SESSION.fullmatch( f ):
				id = int( m.groups()[0] )
				if id not in ids:
					resource = PolarFlowTakeoutImporter.json_handler.load( fs=fs, path=f )

		return []
