from flask import Flask
from models import db
from routes import app as routes_blueprint
import json
from flask_migrate import Migrate
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import ollama
from sqlalchemy import create_engine, MetaData
from helper import configure_genai,  extract_pdf_text
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI
api_key = os.getenv("GOOGLE_API_KEY")
configure_genai(api_key)

app = Flask(__name__)

# Configure app from environment variables
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS")

# Initialize Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)


# Initialize Database
db.init_app(app)
migrate = Migrate(app, db)

# Register Routes
app.register_blueprint(routes_blueprint)


# Add 'fromjson' filter to the Jinja environment
app.jinja_env.filters['fromjson'] = json.loads

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create database tables
        engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI")) # Or your database URL
        metadata = MetaData()
        metadata.reflect(bind=engine) # reflect the already existing tables.
        with open("schema.sql", "w") as f:
            for table in metadata.sorted_tables:
                f.write(str(table.compile(engine.dialect)) + ";\n")
                for column in table.columns:
                    if column.foreign_keys:
                        for fk in column.foreign_keys:
                            f.write(str(fk.compile(engine.dialect)) + ";\n")
    app.run(debug=True)
