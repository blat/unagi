from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

# Connecting
engine = create_engine('sqlite:////path/to/unagi/unagi.db', echo=False)

# Creating a Session
session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Declare a Mapping
Base = declarative_base()
