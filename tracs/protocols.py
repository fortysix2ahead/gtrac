
from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Protocol
from typing import Tuple
from typing import Type
from typing import Union

from .activity import Activity
from .config import ApplicationContext
from .resources import Resource

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

class Handler( Protocol ):
	"""
	A handler defines the protocol for loading and saving documents, transforming them into a dict-like structure.
	Example: input can be a string, containing a GPX XML and the output is the parsed GPX structure.
	"""

	def load( self, path: Optional[Path] = None, data: Optional[Union[str, bytes]] = None ) -> Union[Dict, Any]:
		"""
		Loads data either from the given path or the given string/byte array.

		:param path: path to load data from
		:param data: data to be used for transformation into a dict
		:return: loaded data (preferably a dict, but could also be any data structure)
		"""
		pass

	# noinspection PyMethodMayBeStatic
	def load_raw( self, path: Path ) -> Any:
		with open( path, encoding='utf-8', mode='r', buffering=8192 ) as p:
			return p.read()

	def save( self, path: Path, data: Union[Dict, str, bytes] ) -> None:
		pass

	def types( self ) -> List[str]:
		pass

class Importer( Protocol ):
	"""
	An importer is used to transform a (preferably) dict-like data structure into an activity or resource.
	"""

	def load( self, path: Optional[Path] = None, url: Optional[str] = None, **kwargs ) -> Optional[Resource]:
		"""
		Loads data from a (remove) source as transforms this data into either an activity or at least into some kind of structured data.

		:param path: local path to load data from, takes precedence over url parameter
		:param url: URL to load data from
		:param kwargs: additional parameters for implementers of this protocol
		:return: loaded data (an activity or structured data like dict)
		"""
		pass

	def load_as_activity( self, path: Optional[Path] = None, url: Optional[str] = None, **kwargs ) -> Optional[Activity]:
		pass

	@property
	def type( self ) -> Optional[str]:
		"""
		Content type this importer supports.

		:return: content type
		"""
		return None

	@property
	def activity_cls( self ) -> Optional[Type[Activity]]:
		"""
		Optional activity class this importer creates when loading resources.
		If this property is not None an activity will be returned when calling the load method.

		:return: activity class
		"""
		return None

class Exporter( Protocol ):
	"""
	The opposite of an importer, used to transform an activity into a dict-like structure.
	"""

	def save( self, data: Any, path: Optional[Path] = None, url: Optional[str] = None, **kwargs ) -> Optional[Resource]:
		"""
		Saves provided data to a path or a URL or returns it as a resource if both parameters are missing.

		"""
		pass
