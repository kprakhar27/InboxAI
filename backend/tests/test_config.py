import os
import sys
import unittest
from unittest import mock

# Add parent directories to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)

# Add to path
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

class TestConfigStructure(unittest.TestCase):
    """Tests for the config.py module"""
    
    def setUp(self):
        """Set up test environment"""
        self.config_path = os.path.join(backend_dir, 'config.py')
        # Check that the file exists
        self.assertTrue(os.path.exists(self.config_path), f"config.py file doesn't exist at {self.config_path}")
        
        # Read file content once
        with open(self.config_path, 'r') as file:
            self.content = file.read()
    
    def test_module_imports(self):
        """Test that necessary modules are imported"""
        # Check for required imports
        required_imports = [
            'import os',
            'from os.path import dirname, join',
            'from dotenv import load_dotenv'
        ]
        
        for imp in required_imports:
            self.assertIn(imp, self.content)
    
    def test_dotenv_setup(self):
        """Test dotenv setup"""
        # Check for dotenv setup
        dotenv_setup = [
            'dotenv_path = join(dirname(__file__), ".env")',
            'load_dotenv(dotenv_path)'
        ]
        
        for line in dotenv_setup:
            self.assertIn(line, self.content)
    
    def test_database_variables(self):
        """Test database environment variables"""
        # Check for database variables
        db_vars = [
            'DB_USER = os.environ.get("DB_USER")',
            'DB_PASSWORD = os.environ.get("DB_PASSWORD")',
            'DB_HOST = os.environ.get("DB_HOST")',
            'DB_PORT = os.environ.get("DB_PORT")',
            'DB_NAME = os.environ.get("DB_NAME")'
        ]
        
        for var in db_vars:
            self.assertIn(var, self.content)
    
    def test_config_class_definition(self):
        """Test Config class definition"""
        # Check for Config class
        class_def = [
            'class Config:',
            'SECRET_KEY = os.environ.get("SECRET_KEY")',
            'JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")',
            'SQLALCHEMY_DATABASE_URI =',
            'f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"',
            'SQLALCHEMY_TRACK_MODIFICATIONS = False'
        ]
        
        for line in class_def:
            self.assertIn(line, self.content)

if __name__ == "__main__":
    unittest.main()




