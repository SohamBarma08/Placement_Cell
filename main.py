from flask import Flask
from config import Config
from models import db
from routes import app as routes_blueprint
import json
from flask_migrate import Migrate
import cloudinary
import cloudinary.uploader
import cloudinary.api
from config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME


# Cloudinary configuration
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

app = Flask(__name__)
app.config.from_object(Config)

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
    app.run(debug=True)
