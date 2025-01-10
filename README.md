# Alembic
## Setup

Init
```
alembic init alembic
```
Configuration of alembic.ini and alembic/env.py to manage by default the stash-ai.default.sqlite3 (managing the schema only)

Create empty revision (init)

```
alembic revision -m 'Init'
alembic upgrade head
```

## To create new revision

```
alembic revision -m 'COMMENT'
#Update the default DB (schema)
alembic upgrade head
```

# Special File
## config.json

This file is NOT commited in the git repository but it contains the passwords for the database and zip files. Be carefull with the content of this file.

# TODO
- [x] Alembic init