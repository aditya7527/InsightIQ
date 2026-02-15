from app.db.session import engine
from app.models import metadata

def init_db():
    metadata.create_all(bind=engine)

if __name__ == '__main__':
    init_db()
    print('DB metadata tables created')
