

from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Protocol
from typing import Tuple
from typing import Union

from .activity import Activity
from .resources import Resource
from .config import ApplicationContext

log = getLogger( __name__ )

class ActivityProtocol( Protocol ):

	def as_activity( self ) -> Activity:
		pass

# protocol for a service -> todo: should be stripped down, not all methods are necessary

class Plugin( Protocol ):

	# getting/setting configuration values

	def cfg_value( self, key: str ) -> Any:
		pass

	def state_value( self, key: str ) -> Any:
		pass

	def set_cfg_value( self, key: str, value: Any ) -> None:
		pass

	def set_state_value( self, key: str, value: Any ) -> None:
		pass

class Service( Protocol ):

	def path_for_id( self, local_id: int, base_path: Optional[Path] ) -> Path:
		"""
		Returns the path in the local db for the provided local id. If the base_path is
		provided, the method returns an abolute path, if not a path relative to the db path
		of the service.

		Example: local_id = 1001, return value = '1/0/0/1001'
		:return: path for the provided local id
		"""
		pass

	def path_for( self, activity: Activity = None, resource: Resource = None, ignore_overlay: bool = True ) -> Optional[Path]:
		pass

	def link_for( self, activity: Optional[Activity], resource: Optional[Resource], ext: Optional[str] = None ) -> Optional[Path]:
		pass

	def url_for( self, activity: Optional[Activity] = None, resource: Optional[Resource] = None, local_id: Optional[int] = None ) -> Optional[str]:
		pass

	def url_for_id( self, local_id: Union[int, str] ) -> str:
		pass

	def url_for_resource_type( self, local_id: Union[int, str], type: str ):
		pass

	def fetch( self, force: bool, pretend: bool, **kwargs ) -> List[Resource]:
		"""
		This method has to be implemented by a service class. It shall fetch information for
		activities from an external service and return a list of summary resources. This way it can be checked
		what activities exist and which identifier they have.

		:param force: flag to signal force execution
		:param pretend: pretend flag, do not persist anything
		:param kwargs: additional parameters
		:return: list of fetched summary resources
		"""
		pass

	def fetch_ids( self ) -> List[int]:
		pass

	def download( self, activity: Optional[Activity] = None, summary: Optional[Resource] = None, force: bool = False, pretend: bool = False, **kwargs ) -> List[Resource]:
		"""
		Downloads related resources like GPX recordings based on a provided activity or summary resource.
		TODO: create a method for all services to ease implementation of subclasses.

		:param activity: activity
		:param summary: summary resource
		:param force: flag force
		:param pretend: pretend flag
		:param kwargs: additional parameters
		:return: a list of downloaded resources
		"""
		pass

	def download_resource( self, resource: Resource, **kwargs ) -> Tuple[Any, int]:
		"""
		Downloads a single resource and returns the content + a status to signal that something has gone wrong.

		:param resource: resource to be downloaded
		:param kwargs: additional parameters
		:return: tuple containing the content + status
		"""
		pass

	def persist_resource_data( self, activity: Activity, force: bool, pretend: bool, **kwargs ) -> None:
		pass

	def postprocess( self, activity: Optional[Activity], resources: Optional[List[Resource]], **kwargs ) -> None:
		pass

	def upsert_activity( self, activity: Activity, force: bool, pretend: bool, **kwargs ) -> None:
		pass

	def import_activities( self, force: bool = False, pretend: bool = False, **kwargs ):
		pass

	def link( self, activity: Activity, resource: Resource, force: bool, pretend: bool ) -> None:
		pass

	def setup( self, ctx: ApplicationContext ) -> None:
		pass
