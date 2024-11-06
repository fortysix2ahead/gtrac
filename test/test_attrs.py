from typing import Any

from attrs import define, field, fields

def to_int( obj, fld, value ) -> int:
	return int( value )

def to_int_conv( value ) -> int:
	return int( value ) if value else None

@define
class ClassUnderTest:

	f1: int = field( default=None, on_setattr=to_int )
	f2: int = field( default=None, converter=to_int_conv )
	f3: int = field()

	@f3.default
	def _f3( self ):
		return self.f2 * 2 if self.f2 else None

def test_attrs_set():
	c = ClassUnderTest()
	assert c.f1 is None

	c = ClassUnderTest( f1='10' )
	assert c.f1 == '10' # on_set is NOT called after instance creation
	c = ClassUnderTest( f2='10' )
	assert c.f2 == 10 # the converter is called

	c = ClassUnderTest()
	c.f1 = '10'
	assert c.f1 == 10
	c.f2 = '10'
	assert c.f2 == 10
	assert c.f3 == 20

# test extended field

def meta_field( *args, **kwargs ) -> Any:
	return field( *args, **( kwargs | { 'metadata': { 'key': 'value' } } ) )

@define
class ClassTwo:

	m: int = meta_field( default=20 )

def test_attrs_metafield():
	c = ClassTwo()
	assert c.m == 20
	assert 'm' in [f.name for f in fields( ClassTwo )]
