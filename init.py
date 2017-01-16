from database import Base, engine
from unagi.show import Show
from unagi.user import User

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
