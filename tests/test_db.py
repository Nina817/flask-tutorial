import sqlite3

import pytest
from flaskr.db import get_db


def test_get_close_db(app):
    with app.app_context(): #we connect to the db and test the connection is the same each time
        db = get_db()
        assert db is get_db()

    with pytest.raises(sqlite3.ProgrammingError) as e: #in the context above we opened the db, after the context it should be closed, so db.execute(...) should raise an error
        db.execute('SELECT 1')

    assert 'closed' in str(e.value)

def test_init_db_command(runner, monkeypatch):
    class Recorder(object):
        called= False
    
    def fake_init_db():
        Recorder.called =  True

    monkeypatch.setattr('flaskr.db.init_db', fake_init_db)
    result = runner.invoke(args=['init-db'])
    assert 'Initialized' in result.output
    assert Recorder.called