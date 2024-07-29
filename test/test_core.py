from datetime import datetime
from inspect import *
from typing import ClassVar, List

from attrs import define, field
from babel.numbers import format_decimal
from pytest import raises

from tracs.core import vproperty, FormattedField, FormattedFields, FormattedFieldsBase, Metadata, VirtualField, VirtualFields, VirtualFieldsBase

def test_virtual_field():

	vf = VirtualField( 'one', int, default=10, display_name='One', description='Field One' )
	assert vf.name == 'one' and vf.type == int and vf.display_name == 'One' and vf.description == 'Field One'
	assert vf() == 10

	vf = VirtualField( 'two', str, factory=lambda v: 'two', display_name='Two', description='Field Two' )
	assert vf.name == 'two' and vf.type == str and vf.display_name == 'Two' and vf.description == 'Field Two'
	assert vf() == 'two'

	vf = VirtualField( 'three', str, default=10, factory=lambda v: 'three', display_name='Three', description='Field Three' )
	assert vf.name == 'three' and vf.type == str and vf.display_name == 'Three' and vf.description == 'Field Three'
	assert vf() == 10 # default value wins over lambda

	vf = VirtualField( 'two', str )
	with raises( AttributeError ):
		assert vf() == 'two'

def test_virtual_fields():

	# test class enriched with virtual fields
	@define
	class ClassWithVirtualFields( VirtualFieldsBase ):

		name: str = field( default='Name' )
		id: id = field( default=1 )
		__internal_name__: str = field( default='Internal Name', alias='__internal_name__' )

	vf = ClassWithVirtualFields.__vf__

	vf.add( VirtualField( 'index', int, default=10, expose=True ) )
	vf.add( VirtualField( 'internal_index', int, default=20 ) )
	vf.add( VirtualField( 'upper_name', str, factory=lambda p: p.name.upper(), expose=True ) )

	cvf = ClassWithVirtualFields()

	assert cvf.name == 'Name'
	assert cvf.upper_name == 'NAME'
	assert cvf.index == 10
	with raises( AttributeError ): # internal index is not exposed as property
		assert cvf.internal_index == 20
	with raises( AttributeError ):
		assert cvf.__another_name__ == 'Another name' # another name is unknown

	# access via vf field - dict-like
	with raises( KeyError ):
		assert cvf.vf['name'] == 'Name' # name is not a virtual field
	assert cvf.vf['upper_name'] == 'NAME'
	assert cvf.vf['index'] == 10
	assert cvf.vf['internal_index'] == 20

	# access via vf field
	with raises( AttributeError ):
		assert cvf.vf.name == 'Name' # name is not a virtual field
	assert cvf.vf.upper_name == 'NAME'
	assert cvf.vf.index == 10
	assert cvf.vf.internal_index == 20 # internal index works this time
	with raises( AttributeError ):
		assert cvf.vf.__another_name__ == 'Another name' # still unknown

	assert 'upper_name' in cvf.vf and 'index' in cvf.vf and 'internal_index' in cvf.vf

	assert 'index' in cvf.vf.keys()
	# assert 20 in cvf.vf.values()
	# assert ('index', 10) in cvf.vf.items()

	names = ClassWithVirtualFields.field_names()
	assert names == ['name', 'id']

	# same as default above
	names = ClassWithVirtualFields.field_names( include_internal=False, include_virtual=False, include_unexposed=False )
	assert names == ['name', 'id']

	names = ClassWithVirtualFields.field_names( include_internal=True, include_virtual=False, include_unexposed=False )
	assert names == ['name', 'id', '__internal_name__' ]

	names = ClassWithVirtualFields.field_names( include_internal=False, include_virtual=True, include_unexposed=False )
	assert names == ['name', 'id', 'index', 'upper_name' ]

	names = ClassWithVirtualFields.field_names( include_internal=False, include_virtual=False, include_unexposed=True )
	assert names == ['name', 'id']

	names = ClassWithVirtualFields.field_names( include_internal=False, include_virtual=True, include_unexposed=True )
	assert names == ['name', 'id', 'index', 'internal_index', 'upper_name' ]

	names = ClassWithVirtualFields.field_names( include_internal=True, include_virtual=True, include_unexposed=True )
	assert names == ['name', 'id', '__internal_name__', 'index', 'internal_index', 'upper_name']

def test_formatted_field():

	ff = FormattedField( name='lower', formatter=lambda v, f, l: v.lower() )
	assert ff( "TEST" ) == 'test'
	assert ff.__format__( "TEST" ) == 'test'

	# test babel fields
	ffe = FormattedField( name='en_int', formatter=lambda v, f, l: format_decimal( v, f, l ), locale='en' )
	ffd = FormattedField( name='en_de', formatter=lambda v, f, l: format_decimal( v, f, l ), locale='de' )

	assert ffe( 1000 ) == '1,000'
	assert ffd( 1000 ) == '1.000'

def test_formatted_fields():

	ffs = FormattedFields()
	ffs['lower'] = lambda v, f, l: v.lower()
	ffs['upper'] = FormattedField( name='upper', formatter=lambda s: s.upper() )

	assert 'lower' in ffs.__fields__ and type( ffs.__fields__.get( 'lower' ) ) is FormattedField
	assert 'upper' in ffs.__fields__ and type( ffs.__fields__.get( 'upper' ) ) is FormattedField

	@define
	class FormattedDataclass( FormattedFieldsBase ):

		name: str = field( default = 'Name' )
		age: int = field( default=10 )
		speed: float = field( default=12345.6 )
		width: float = field( default=None )

	FormattedDataclass.__fmf__['name'] = lambda v, f, l: v.lower()
	FormattedDataclass.__fmf__.add( FormattedField( name='speed', formatter=lambda v, f, l: format_decimal( v, f, l ), locale='en' ) )

	fdc = FormattedDataclass()

	assert fdc.fmf.name == 'name'
	assert fdc.fmf.age == 10
	assert fdc.fmf.speed == '12,345.6'

	with raises( AttributeError ):
		assert fdc.fmf.noexist == 0

	assert fdc.fmf.as_list( 'name', 'age', 'speed', 'width' ) == ['name', 10, '12,345.6', None]

	with raises( AttributeError ):
		assert fdc.fmf.as_list( 'name', 'age', 'speed', 'height' ) == ['name', 10, '12,345.6', None]

	assert fdc.fmf.as_list( 'name', 'age', 'speed', 'height', suppress_error=True ) == ['name', 10, '12,345.6', None]
	assert fdc.fmf.as_list( 'name', 'age', 'speed', 'width', converter=lambda v: str( v ) ) == ['name', '10', '12,345.6', 'None']

def test_metadata():

	md = Metadata(
		uid='polar:101',
		created=datetime( 2023, 6, 1, 10, 0, 0 ),
		modified=datetime( 2023, 7, 2, 11, 0, 0 ),
		f1='one',
	)

	md.f2 = 'two'
	md['f3'] = 'three'

	assert len( md ) == 6
	assert md.uid == 'polar:101'
	assert md.f2 == 'two'
	assert md['f3'] == 'three'

	assert md.keys() == ['uid', 'created', 'modified', 'f1', 'f2', 'f3']
	assert md.values() == [
		'polar:101',
		datetime( 2023, 6, 1, 10, 0, 0 ),
		datetime( 2023, 7, 2, 11, 0, 0 ),
		'one',
		'two',
		'three',
	]
	assert md.items() == [
		('uid', 'polar:101'),
		('created', datetime( 2023, 6, 1, 10, 0, 0 )),
		('modified', datetime( 2023, 7, 2, 11, 0, 0 )),
		('f1', 'one'),
		('f2', 'two'),
		('f3', 'three'),
	]
	assert md.as_dict() == {
		'uid': 'polar:101',
		'created': datetime( 2023, 6, 1, 10, 0, 0 ),
		'modified': datetime( 2023, 7, 2, 11, 0, 0 ),
		'f1': 'one',
		'f2': 'two',
		'f3': 'three',
	}
