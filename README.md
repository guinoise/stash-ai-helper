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
### Shell (bash/sh)

Set the variable COMMENT :

```
COMMENT=""
```

Generate revision 
```
alembic revision --autogenerate -m "${COMMENT}"
```

Apply to the default database
```
alembic upgrade head
```

### Powershell

Set the variable COMMENT :

```
$COMMENT=""
```

Generate revision 
```
alembic revision --autogenerate -m "$COMMENT"
```

Apply to the default database
```
alembic upgrade head
```

# Special File
## config.json

This file is NOT commited in the git repository but it contains the passwords for the database and zip files. Be carefull with the content of this file.

# TODO
- [X] Alembic init
- [ ] Fix the logger format
