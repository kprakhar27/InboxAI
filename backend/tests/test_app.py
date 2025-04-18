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

class TestAppStructure(unittest.TestCase):
    """Tests for the app.py module"""
    def setUp(self):
        """Set up test environment"""
        self.app_path = os.path.join(backend_dir, 'app.py')
        # Check that the file exists
        self.assertTrue(os.path.exists(self.app_path), f"app.py file doesn't exist at {self.app_path}")
        
        # Read file content once
        with open(self.app_path, 'r') as file:
            self.content = file.read()
    
    def test_module_imports(self):
        """Test that necessary modules are imported"""
        # Check for required imports
        required_imports = [
            'from app import create_app'
        ]
        
        for imp in required_imports:
            self.assertIn(imp, self.content)
    
    def test_app_initialization(self):
        """Test Flask app initialization"""
        # Check for app initialization
        app_init = [
            'app = create_app()',
        ]
        
        for line in app_init:
            self.assertIn(line, self.content)
    
    def test_main_block(self):
        """Test main execution block"""
        # Check for main block
        main_block = [
            'if __name__ == "__main__":',
            'app.run(',
            'host="0.0.0.0"',
            'port=6000',
            'debug=True'
        ]
        
        for line in main_block:
            self.assertIn(line, self.content)

if __name__ == "__main__":
    unittest.main()

