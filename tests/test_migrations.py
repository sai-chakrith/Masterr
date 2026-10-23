from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from backend.db import Base, make_engine


def test_schema_upgrade_downgrade_reupgrade_and_metadata_match(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "migrations.db")
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.connect() as connection:
        assert "attempts" in inspect(connection).get_table_names()
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()
    command.downgrade(config, "base")
    engine = make_engine(url)
    assert "attempts" not in inspect(engine).get_table_names()
    engine.dispose()
    command.upgrade(config, "head")
    engine = make_engine(url)
    assert "reviews" in inspect(engine).get_table_names()
    engine.dispose()


def test_postgresql_migration_compiles_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/mastrr")
    sql_path = tmp_path / "postgres.sql"
    with sql_path.open("w") as output:
        config = Config("alembic.ini", output_buffer=output)
        command.upgrade(config, "head", sql=True)
    sql = sql_path.read_text()
    assert "CREATE TABLE attempts" in sql
    assert "CREATE TABLE reviews" in sql
    assert "FOREIGN KEY" in sql
