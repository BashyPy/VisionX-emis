# Import the relevant functions from functions.py
from functions import (
    init_db, log_event, connect_to_google_sheet, fetch_db_data, update_google_sheet_from_db,
    log_scan_activity, create_qr_code, validate_phone_and_emergency_contact, validate_nin,
    validate_phone, validate_emergency_contact, get_patient_by_id, insert_or_update_patient,
    display_first_aid_guide_auto_scroll_with_manual
)
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from io import BytesIO
import os
import sys

# Ensure the parent directory is in the system path for imports
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


class TestFunctions(unittest.TestCase):

    @patch('sqlite3.connect')
    def test_init_db(self, mock_connect):
        """ Test initialization of database. """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        init_db()
        mock_connect.assert_called_once_with('patients.db')
        mock_conn.cursor().execute.assert_called_once()

    @patch('sqlite3.connect')
    def test_log_event(self, mock_connect):
        """ Test logging events to the database. """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        log_event('INFO', 'Test log message')
        mock_connect.assert_called_once_with('patients.db')
        mock_conn.cursor().execute.assert_called_once_with(
            'INSERT INTO logs (level, message) VALUES (?, ?)', ('INFO', 'Test log message'))

    @patch('functions.gspread.authorize')
    @patch('functions.ServiceAccountCredentials.from_json_keyfile_name')
    def test_connect_to_google_sheet(self, mock_credentials, mock_authorize):
        """ Test connecting to Google Sheets. """
        mock_client = MagicMock()
        mock_authorize.return_value = mock_client
        mock_worksheet = MagicMock()
        mock_client.open_by_key.return_value.worksheet.return_value = mock_worksheet

        sheet_id = "dummy_sheet_id"
        sheet_name = "dummy_sheet_name"
        result = connect_to_google_sheet(sheet_id, sheet_name)
        self.assertEqual(result, mock_worksheet)

    @patch('sqlite3.connect')
    def test_fetch_db_data(self, mock_connect):
        """ Test fetching data from the SQLite database. """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = mock_conn.cursor()
        mock_cursor.execute.return_value.fetchall.return_value = [
            (1, 'John Doe', 30)]

        query = "SELECT * FROM patients"
        result = fetch_db_data(query)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(result.iloc[0, 1], 'John Doe')
        mock_connect.assert_called_once_with('patients.db')

    @patch('sqlite3.connect')
    @patch('functions.update_google_sheet_from_db')
    def test_log_scan_activity(self, mock_update_google_sheet, mock_connect):
        """ Test logging scan activities without IP. """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_scan_worksheet = MagicMock()
        log_scan_activity('dummy_uuid', mock_scan_worksheet)
        mock_connect.assert_called_once_with('patients.db')
        mock_conn.cursor().execute.assert_called_once_with(
            'INSERT INTO scan_activities (patient_uuid) VALUES (?)', ('dummy_uuid',))
        mock_update_google_sheet.assert_called_once_with(mock_conn)

    @patch('os.makedirs')
    def test_create_qr_code(self, mock_makedirs):
        """ Test QR code generation with the correct path and data. """
        mock_file_path = "dummy/path/qr_code.png"
        data = "https://example.com"
        mock_makedirs.return_value = None
        result = create_qr_code(data, mock_file_path)
        self.assertIsInstance(result, BytesIO)

    def test_validate_phone_and_emergency_contact(self):
        """ Test validation to ensure phone number and emergency contact are not the same. """
        phone = "+2341234567890"
        emergency_contact = "+2340987654321"
        result = validate_phone_and_emergency_contact(phone, emergency_contact)
        self.assertTrue(result)
        result_fail = validate_phone_and_emergency_contact(phone, phone)
        self.assertFalse(result_fail)

    def test_validate_nin(self):
        """ Test NIN validation to ensure it is 11 digits. """
        valid_nin = "12345678901"
        invalid_nin = "12345"
        self.assertTrue(validate_nin(valid_nin))
        self.assertFalse(validate_nin(invalid_nin))

    def test_validate_phone(self):
        """ Test phone number validation for Nigerian numbers. """
        phone = "08123456789"
        result = validate_phone(phone)
        self.assertEqual(result, "+2348123456789")

    def test_validate_emergency_contact(self):
        """ Test emergency contact validation. """
        emergency_contact = "07031234567"
        result = validate_emergency_contact(emergency_contact)
        self.assertEqual(result, "+2347031234567")

    @patch('sqlite3.connect')
    def test_get_patient_by_id(self, mock_connect):
        """ Test fetching patient by ID. """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.fetchone.return_value = (
            1, 'uuid', 'John Doe', 25)

        patient_id = "PAT123"
        result = get_patient_by_id(patient_id)
        self.assertIsNotNone(result)
        self.assertEqual(result[2], 'John Doe')

    @patch('sqlite3.connect')
    def test_insert_or_update_patient(self, mock_connect):
        """ Test inserting or updating a patient's information. """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_worksheet = MagicMock()

        name = "John Doe"
        age = 25
        nin = "12345678901"
        phone = "+2341234567890"
        emergency_contact = "+2340987654321"
        genotype = "AA"
        blood_type = "O+"
        new_allergies = "Peanuts"
        new_medical_history = "Asthma"
        patient_id = "PAT123"
        result = insert_or_update_patient(name, age, nin, phone, emergency_contact, genotype, blood_type,
                                          new_allergies, new_medical_history, patient_id, mock_worksheet, None)
        self.assertIsNotNone(result)
        mock_connect.assert_called_once_with('patients.db')

    # Bypass sleep for faster tests
    @patch('functions.time.sleep', return_value=None)
    def test_display_first_aid_guide_auto_scroll_with_manual(self, _mock_sleep):
        """ Test the display of the first aid guide with auto-scroll. """
        with patch('streamlit.markdown') as mock_markdown:
            display_first_aid_guide_auto_scroll_with_manual()
            self.assertTrue(mock_markdown.called)


if __name__ == "__main__":
    unittest.main()
