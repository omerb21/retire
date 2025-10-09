from app.database import engine, Base

def update_database():
    # This will update the database schema based on the models
    Base.metadata.create_all(bind=engine)
    print("Database schema updated")

if __name__ == "__main__":
    update_database()
