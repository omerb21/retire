# Bulk delete + SQLAlchemy identity map (Do/Don't)

Do: If you loaded ORM instances and then do a bulk `delete(..., synchronize_session=False)`, either avoid pre-loading or `expunge()` the instances you loaded.

Don’t: Don’t create/add a new ORM instance with a PK that already exists in the current Session identity map.

Rule of thumb: Bulk delete is a DB operation; if the Session already holds identities for that model, choose one: a suitable `synchronize_session`, `expunge`, or don’t load first.
