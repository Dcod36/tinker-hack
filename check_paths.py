import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.config import config
    from app.models.database import DB_PATH
    
    print(f"ABS DB_PATH: {os.path.abspath(DB_PATH)}")
    print(f"ABS UPLOAD_FOLDER: {os.path.abspath(config.UPLOAD_FOLDER)}")
    
    # Check if they exist
    print(f"DB EXISTS: {os.path.exists(DB_PATH)}")
    print(f"UPLOAD FOLDER EXISTS: {os.path.exists(config.UPLOAD_FOLDER)}")
    
    # List files in upload folder
    if os.path.exists(config.UPLOAD_FOLDER):
        print(f"FILES IN UPLOAD FOLDER: {os.listdir(config.UPLOAD_FOLDER)}")
    else:
        print("UPLOAD FOLDER DOES NOT EXIST")
        
except Exception as e:
    print(f"Error: {e}")
