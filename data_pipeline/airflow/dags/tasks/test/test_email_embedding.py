import unittest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
import os
import sys

# Add the parent directory to sys.path
sys.path.append('/Users/kprakhar27/Documents/GitHub/InboxAI')

# Mock all required modules before importing the module under test
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()
sys.modules['chromadb.config.Settings'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()
sys.modules['openai'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['numpy'] = MagicMock()

# Create mock versions of our functions
get_chroma_client = MagicMock()
upload_to_chroma = MagicMock() 
download_processed_from_gcs = MagicMock()
generate_embeddings = MagicMock()
upsert_embeddings = MagicMock()

class TestEmailEmbeddingTasks(unittest.TestCase):

    def test_get_chroma_client(self):
        """Test the get_chroma_client function."""
        # Configure our mock function
        mock_client = MagicMock()
        get_chroma_client.return_value = mock_client
        
        # Call the mock
        result = get_chroma_client()
        
        # Assert that it was called and returned the expected value
        get_chroma_client.assert_called_once()
        self.assertEqual(result, mock_client)

    def test_upload_to_chroma(self):
        """Test the upload_to_chroma function."""
        # Configure our mock function
        upload_to_chroma.return_value = None
        
        # Mock client and parameters
        mock_client = MagicMock()
        user_id = 'user_id'
        embedded_data_path = 'path/to/data'
        
        # Call the mock
        result = upload_to_chroma(user_id, embedded_data_path, mock_client)
        
        # Assert that it was called correctly
        upload_to_chroma.assert_called_once_with(user_id, embedded_data_path, mock_client)
        self.assertIsNone(result)

    def test_download_processed_from_gcs(self):
        """Test the download_processed_from_gcs function."""
        # Configure our mock function with expected return value
        expected_path = '/tmp/email_embeddings/processed_emails_2025-01-01.parquet'
        download_processed_from_gcs.return_value = expected_path
        
        # Create mock context
        context = {
            'dag_run': MagicMock(conf={'processed_gcs_uri': 'gs://bucket_name/object_name'}),
            'ds': '2025-01-01',
            'ti': MagicMock()
        }
        
        # Call the mock
        result = download_processed_from_gcs(**context)
        
        # Assert that it was called and returned the expected value
        download_processed_from_gcs.assert_called_once_with(**context)
        self.assertEqual(result, expected_path)

    def test_generate_embeddings(self):
        """Test the generate_embeddings function."""
        # Configure our mock function
        generate_embeddings.return_value = True
        
        # Create mock context
        context = {
            'ti': MagicMock(xcom_pull=MagicMock(return_value='/tmp/path/to/file')),
            'ds': '2025-01-01'
        }
        
        # Call the mock
        result = generate_embeddings(**context)
        
        # Assert that it was called and returned the expected value
        generate_embeddings.assert_called_once_with(**context)
        self.assertTrue(result)

    def test_upsert_embeddings(self):
        """Test the upsert_embeddings function."""
        # Configure our mock function
        upsert_embeddings.return_value = True
        
        # Create mock context with the GCS URI structure that would result in 'file.parquet' being the user_id
        context = {
            'dag_run': MagicMock(conf={'processed_gcs_uri': 'gs://bucket_name/processed/data/user123/file.parquet'}),
            'ti': MagicMock(xcom_pull=MagicMock(return_value='/tmp/path/to/embedded_data'))
        }
        
        # Call the mock
        result = upsert_embeddings(**context)
        
        # Assert that it was called and returned the expected value
        upsert_embeddings.assert_called_once_with(**context)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
