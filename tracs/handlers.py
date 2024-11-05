
from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Optional, Type, Union

from fs.base import FS
from fs.osfs import OSFS
from requests import Response, Session

from tracs.activity import Activity
from tracs.resources import Resource, Resources
from tracs.utils import abspath

log = getLogger( __name__ )

class ResourceHandler:

	# todo: remove resource_type in favour of TYPE
	resource_type: Optional[str] = None
	TYPE: Optional[str] = resource_type
	ACTIVITY_CLS: Optional[Type] = None

	def __init__( self, resource_type: Optional[str] = None, activity_cls: Optional[Type] = None ) -> None:
		self._type: Optional[str] = resource_type
		self._activity_cls: Optional[Type] = activity_cls
		self._factory: Callable = self.transform_data
		self._osfs: OSFS = OSFS( '/' )

		# todo: are these fields really needed? probably not ...
		self.resource: Optional[Resource] = None
		self.content: Optional[Union[bytes,str]] = None
		self.raw: Any = None
		self.data: Any = None

	def load( self, path: Path|str = None, url: str = None, content: bytes|str = None, fs: FS = None, **kwargs ) -> Optional[Resource]:
		# load from either from path, fs or url, if neither is provided use content
		if path and not fs:
			fs, path = self._osfs, abspath( path )

		if path and fs:
			content = self.load_from_fs( fs, path, **kwargs )
		elif url:
			content = self.load_from_url( url, **kwargs )
		else:
			content = self.load_from_content( content, **kwargs ) # todo: do we really need this or just reuse provided content?

		# try to transform content into structured data (i.e. from bytes to a dict)
		# by default this does nothing and has to be implemented in subclasses
		raw = self.load_raw( content, **kwargs )

		# postprocess data, transform from raw into structured data
		data = self.load_data( raw, **kwargs )

		# return the result
		return self.load_resource( fs, path, url, content=content, raw=raw, data=data, **kwargs )

	def load_as_activity( self, path: Path|str = None, url: str = None, content: bytes|str = None, fs: FS = None, **kwargs ) -> Activity:
		"""This is basically the same as load(), but transforms the loaded activity into a resource.
		This calls load() and provides the loaded resource to as_activity() and returns the result.
		In addition, it's possible to provide a resource as kwarg. In this case the content/raw/data from the resource
		will be used to construct the activity or the resource will be populated.
		"""
		resource = kwargs.pop( 'resource', None ) or Resource()
		if resource.content:
			resource = self.load( content=resource.content, resource=resource, **kwargs )
		else:
			resource = self.load( path=path, fs=fs, url=url, content=content, resource=resource, **kwargs )

		return self.as_activity( resource )

	def as_activity( self, resource: Resource ) -> Activity:
		return Activity( resources=Resources( resource ) )

	# load methods

	# noinspection PyMethodMayBeStatic
	def load_from_content( self, content: bytes|str, **kwargs ) -> bytes|str:
		"""
		By default, this does nothing. Only returns the content, subclasses may override.

		:param content: low-level content to read
		:return: bytes or str read from the provided path
		"""
		return content

	# noinspection PyMethodMayBeStatic
	def load_from_path( self, path: str|Path, **kwargs ) -> bytes:
		"""
		Reads from the provided path and returns the files content as bytes.

		:param path: OS path to read from
		:param kwargs: n/a
		:return: bytes read from the provided path
		:raise: FileNotFoundError, ResourceNotFound
		"""
		return self.load_from_fs( self._osfs, str( path ), **kwargs )

	# noinspection PyMethodMayBeStatic
	def load_from_fs( self, fs: FS, path: str, **kwargs ) -> bytes:
		"""
		Reads data from a path in the provided file system.

		:param fs: FS to read from
		:param path:  path to read from
		:param kwargs: n/a
		:return: bytes read from the provided path
		"""
		return fs.readbytes( path )

	# noinspection PyMethodMayBeStatic
	def load_from_url( self, url: str, **kwargs ) -> bytes:
		"""
		Loads data from a url.

		:param url: URL to load data from
		:param kwargs: session, headers, allow_redirects, stream
		:return: bytes read from the provided URL
		"""
		session: Session = kwargs.get( 'session' )
		headers = kwargs.get( 'headers' )
		allow_redirects: bool = kwargs.get( 'allow_redirects', True )
		stream: bool = kwargs.get( 'stream', True )
		response: Response = session.get( url, headers=headers, allow_redirects=allow_redirects, stream=stream )
		return response.content

	def load_raw( self, content: bytes|str, **kwargs ) -> Any:
		"""
		Loads raw data from provided content.
		Example: load a json from a string and return a dict. The default implementation of this method
		returns the content without any transformation. Subclasses should override this method.

		:param content: content to be transformed into structured data
		:return: transformed structured data
		"""
		return content

	def load_data( self, raw: Any, **kwargs ) -> Any:
		"""
		Transforms raw structured data into well-defined structured data.
		Example: raw data is an arbitrary JSON document (a dict), while well-defined data is an instance of GeoJSON.
		The transformation from JSON to an actual GeoJSON object shall be done in this method.
		By default, this method simply return the provided raw data.

		:param raw: structured raw data to be transformed
		:return: well-defined structured data
		"""
		return raw

	# noinspection PyMethodMayBeStatic
	def transform_data( self, raw: Any, **kwargs ):
		return raw

	def load_resource( self, fs: FS, path: str = None, url: str = None, **kwargs ) -> Resource:
		content, raw, data = kwargs.get( 'content' ), kwargs.get( 'raw' ), kwargs.get( 'data' )
		source = kwargs.get( 'source' ) or url
		resource = kwargs.get( 'resource' ) or Resource()

		resource.content, resource.raw, resource.data = content, raw, data
		resource.type = self.__class__.TYPE
		# resource.path = path
		# resource.source = source # todo: we might already set the source depending on FS

		return resource

	# noinspection PyMethodMayBeStatic
	def as_str( self, content: bytes, encoding: str = 'UTF-8' ) -> str:
		return content.decode( encoding )

	# noinspection PyMethodMayBeStatic
	def as_bytes( self, text: str, encoding: str = 'UTF-8' ) -> bytes:
		return text.encode( encoding )

	@property
	def type( self ) -> Optional[str]:
		return self.__class__.TYPE

	@type.setter
	def type( self, value: str ) -> None :
		self._type = value

	@property
	def activity_cls( self ) -> Optional[Type]:
		return self.__class__.ACTIVITY_CLS

	@activity_cls.setter
	def activity_cls( self, cls: Type ) -> None:
		self._activity_cls = cls

	# noinspection PyMethodMayBeStatic
	def save_data( self, data: Any, **kwargs ) -> Any:
		"""
		Transforms structured data into raw data, for instance from a dataclass to a dict.
		By default, this simply returns the data and may be overridden in subclasses.
		"""
		if self._activity_cls:
			try:
				return self._factory.dump( data, self._activity_cls )
			except RuntimeError:
				log.error( f'unable to transform raw data into structured data by using the factory for {self._activity_cls}', exc_info=True )
				return data
		else:
			return data

	def save_raw( self, data: Any, **kwargs ) -> bytes:
		"""
		Transforms raw data into bytes.
		By default, this calls __repr__() and encodes the result with UTF-8.
		This method is supposed to be implemented in subclasses.
		"""
		return data.__repr__().encode( 'UTF-8' )

	# noinspection PyMethodMayBeStatic
	def save_to_path( self, content: bytes, path: Path, **kwargs ) -> None:
		path.write_bytes( content )

	# noinspection PyMethodMayBeStatic
	def save_to_url( self, content: bytes, url: str, **kwargs ) -> None:
		raise NotImplementedError

	# noinspection PyMethodMayBeStatic
	def save_to_resource( self, content, raw, data, **kwargs ) -> Resource:
		return Resource( raw = raw, data = data, content = content, **kwargs )

	def save( self, data: Any, path: Optional[Path] = None, url: Optional[str] = None, **kwargs ) -> Optional[Resource]:
		raw = self.save_data( data )

		content = self.save_raw( raw, **kwargs )

		if path:
			self.save_to_path( content, path, **kwargs )
		elif url:
			self.save_to_url( content, url, **kwargs )

		return self.save_to_resource( content=content, raw=raw, data=data, **kwargs )
