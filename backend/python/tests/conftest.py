import os

# Set a dummy DATABASE_URL for unit tests
# This prevents import errors during test collection when db_utils is imported
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
