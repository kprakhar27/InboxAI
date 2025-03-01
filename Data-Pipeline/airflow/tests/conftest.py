import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Add DAGs directory to path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "dags"))


@pytest.fixture
def mock_context():
    """Create a mock Airflow task context"""
    ti_mock = MagicMock()
    ti_mock.xcom_pull = MagicMock()
    ti_mock.xcom_push = MagicMock()

    dag_run_mock = MagicMock()
    dag_run_mock.conf = {"email_address": "test@example.com", "batch_size": 50}

    return {
        "task_instance": ti_mock,
        "dag_run": dag_run_mock,
        "params": {"email_address": "test@example.com", "batch_size": 50},
    }


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = MagicMock()
    query_mock = MagicMock()
    session.query.return_value = query_mock
    filter_mock = MagicMock()
    query_mock.filter.return_value = filter_mock
    query_mock.filter_by.return_value = filter_mock
    first_mock = MagicMock()
    filter_mock.first.return_value = first_mock
    order_by_mock = MagicMock()
    filter_mock.order_by.return_value = order_by_mock
    order_by_mock.first.return_value = first_mock

    return session
