
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, List

from dataclass_factory import Factory, Schema
from dataclass_wizard import asdict, DumpMeta
from dataclass_wizard.enums import LetterCase
from fs import open_fs
from fs.copy import copy_fs, copy_file
from pathlib import Path
from orjson import loads
from tinydb import TinyDB

from tracs.activity import Activity
from tracs.config import ApplicationContext
from tracs.db import ActivityDb
from tracs.db_storage import DataClassStorage

db_live_path = Path( Path( '~' ).expanduser(), 'Projekte/com.github.tracs.data/db' )
activities_live_path = Path( db_live_path, 'activities.json' )

local_fs = open_fs( '~/Projekte/com.github.tracs.data/db' )
local_json = '~/Projekte/com.github.tracs.data/db/activities.json'

mem_fs = open_fs( 'mem://' )
mem_json = 'mem://activities.json'

ctx = ApplicationContext()
ctx.timeit( skip_print=True )

@dataclass
class Sample:

    dt: datetime = field( default=datetime.utcnow() )
    t: time = field( default=None )

@dataclass
class ActivityDatabase:

    tables: Dict[str, Dict[int, Activity]] = field( default_factory=list )

    def activities( self ) -> Dict[int, Activity]:
        return self.tables.get( '_default' )

    def all_activities( self ) -> List[Activity]:
        return list( self.activities().values() )

def test_read_db():
    ctx.pp( db_live_path )

def test_load_complete_tinydb():
    ctx.timeit( skip_print=True )
    db = ActivityDb( db_live_path )
    ctx.timeit( 'open tiny db (complete)' )

def test_load_tinydb():
    ctx.timeit( skip_print=True )
    db = TinyDB( storage=DataClassStorage, path=activities_live_path, read_only=True, passthrough=True )
    ctx.timeit( 'open tiny db (activities only)' )

def test_dump_factory():
    activity_schema = Schema( exclude=[ 'doc_id', 'type' ], omit_default=True )
    datetime_schema = Schema(
        parser=lambda s: datetime.fromisoformat( s ) if s else None,
        serializer=lambda dt: dt.isoformat() if dt else None
    )
    time_schema = Schema(
        parser=lambda s: time.fromisoformat( s ) if s else None,
        serializer=lambda t: t.isoformat() if t else None
    )
    factory = Factory(
        debug_path=True,
        schemas={
            Activity: activity_schema,
            datetime: datetime_schema,
            time: time_schema
        }
    )

    obj = Activity( doc_id=1, time=datetime.utcnow(), time_end=datetime.utcnow() )
    obj = factory.dump( obj, Activity )
    ctx.pp( obj )

def test_load_factory():
    ctx.timeit( skip_print=True )

    copy_file( local_fs, 'activities.json', mem_fs, 'activities.json' )
    json = loads( mem_fs.readbytes( 'activities.json' ) )

    activity_schema = Schema( exclude=[ 'doc_id', 'type' ], omit_default=True )
    tiny_database_schema = Schema(
        skip_internal = False,
        unknown='tables',
#        name_mapping={'tables': '_default'}
    )

    factory = Factory(
        debug_path=True,
        schemas={
            ActivityDatabase: tiny_database_schema,
            Activity: activity_schema,
        }
    )

    obj = factory.load(json, ActivityDatabase)

    ctx.timeit( message='load via factory' )

    _all = obj.all_activities()
    ctx.pp( obj.activities().get( 111 ) )

def test_dump_wizard():
    obj = Activity( doc_id=1, time=datetime.utcnow(), time_end=datetime.utcnow() )
    DumpMeta( key_transform=LetterCase.SNAKE ).bind_to( Activity )
    obj = asdict( obj, cls=Activity, skip_defaults=True, exclude=[ 'doc_id' ] )
    ctx.pp( obj )
