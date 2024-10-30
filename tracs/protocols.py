
from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Type, Union

log = getLogger( __name__ )

class Resource( Protocol ):

	...

class Activity( Protocol ):

	...

# protocol for a service -> todo: should be stripped down, not all methods are necessary

class Plugin( Protocol ):

	# getting/setting configuration values

	def cfg_value( self, key: str ) -> Any:
		...

	def state_value( self, key: str ) -> Any:
		...

	def set_cfg_value( self, key: str, value: Any ) -> None:
		...

	def set_state_value( self, key: str, value: Any ) -> None:
		...

class Service( Protocol ):

	@property
	def name( self ) -> str:
		"""
		Returns the name of the service.
		The name should only consist of lower-case alphanumeric characters.
		"""
		...

	def path_for_id( self, local_id: Union[int, str], base_path: Optional[str] = None, resource_path: Optional[str] = None ) -> Union[Path, str]:
		"""
		Returns the path in the local db for the provided local id. If the base_path is
		provided, it will be prepended to the path. If a resource path is provided, it will be appended.
		If the local_id has less than 3 characters, zeros are added to the left.

		Examples:
		local_id = 1001, return value = '1/0/0/1001'
		local_id = 1001, base_path = service, resource_path = recording.gpx, return value = 'service/1/0/0/1001/recording.gpx'
		:return: path for the provided local id
		"""
		...

	def path_for( self, resource: Resource, ignore_overlay: bool = True, absolute: bool = True, omit_classifier: bool = False, as_path: bool = True ) -> Union[Path, str]:
		...

	def link_for( self, activity: Optional[Activity], resource: Optional[Resource], ext: Optional[str] = None ) -> Optional[Path]:
		...

	def url_for( self, activity: Optional[Activity] = None, resource: Optional[Resource] = None, local_id: Optional[int] = None ) -> Optional[str]:
		...

	def url_for_id( self, local_id: Union[int, str] ) -> str:
		...

	def url_for_resource_type( self, local_id: Union[int, str], type: str ):
		...

	def import_activities( self, force: bool = False, pretend: bool = False, **kwargs ):
		...

	def link( self, activity: Activity, resource: Resource, force: bool, pretend: bool ) -> None:
		...

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
		...

	# noinspection PyMethodMayBeStatic
	def load_raw( self, path: Path ) -> Any:
		with open( path, encoding='utf-8', mode='r', buffering=8192 ) as p:
			return p.read()

	def save( self, path: Path, data: Union[Dict, str, bytes] ) -> None:
		...

	def types( self ) -> List[str]:
		...

class Importer( Protocol ):
	"""
	An importer is used to transform a (preferably) dict-like data structure into an activity or resource.
	"""

	def load( self, path: Optional[Path|str] = None, url: Optional[str] = None, **kwargs ) -> Resource:
		"""
		Loads data from a (remove) source as transforms this data into either an activity or at least into some kind of structured data.

		:param path: local path to load data from, takes precedence over url parameter, can be absolute or relative (fs needs to be provided)
		:param url: URL to load data from
		:param kwargs: additional parameters for implementers of this protocol, can be fs or resource
		:return: loaded resource
		"""
		...

	def load_as_activity( self, path: Optional[Path|str] = None, url: Optional[str] = None, **kwargs ) -> Optional[Activity]:
		"""
		Loads data via load() and returns it via as_activity()
		"""
		...

	def as_activity( self, resource: Resource ) -> Optional[Activity]:
		"""
		Transforms the provided resource into an activity.
		"""
		...

	@property
	def type( self ) -> Optional[str]:
		"""
		Content type this importer supports.

		:return: content type
		"""
		...

	@property
	def activity_cls( self ) -> Optional[Type[Activity]]:
		"""
		Optional activity class this importer creates when loading resources.
		If this property is not None an activity will be returned when calling the load method.

		:return: activity class
		"""
		...

class Exporter( Protocol ):
	"""
	The opposite of an importer, used to transform an activity into a dict-like structure.
	"""

	def save( self, data: Any, path: Optional[Path|str] = None, url: Optional[str] = None, **kwargs ) -> Optional[Resource]:
		"""
		Saves provided data to a path or a URL or returns it as a resource if both parameters are missing.

		:param data: structured data to be exported
		:param path: path to export to, can be relative or absolute
		:param url: URL to export to
		:param kwargs: additional parameters for implementers of this protocol, can be fs or resource
		:return: loaded resource

		"""
		...
