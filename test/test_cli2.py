from logging import getLogger

from pytest import mark

from helpers import invoke_cli as invoke
from tracs.config import ApplicationContext as Context

log = getLogger( __name__ )

cmd_list = 'list'
cmd_list_1 = 'list 1'
cmd_list_l_1 = 'list -l "id name" 1'

cmd_version = 'version'

# no command

@mark.context( env='default', persist='clone', cleanup=True )
def test_nocommand( ctx: Context ):
	i = invoke( ctx, '' )
	assert i.out == ''
	assert i.err.contains_all( 'Usage', 'Error: Missing command' )

# list

@mark.context( env='default', persist='clone', cleanup=True )
def test_list( ctx: Context ):
	i = invoke( ctx, cmd_list )
	assert i.out.contains( 'Run at Noon' )
	# todo: don't know how to extend the width of the virtual terminal to more than 80 characters
	assert i.out.table_header == [ 'id', 'name', 'type', 'starttime_l…', 'uid', 'uids' ]
	i = invoke( ctx, cmd_list_1 )
	assert i.out.table_header == [ 'id', 'name', 'type', 'starttime_lo…', 'uid', 'uids' ]

	i = invoke( ctx, cmd_list_l_1 )
	assert i.out.table_header == [ 'id', 'name' ]

# version

@mark.context( env='default', persist='clone', cleanup=True )
def test_version( ctx: Context ):
	assert invoke( ctx, cmd_version ).out == '0.1.0'
