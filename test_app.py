import unittest
from unittest.mock import patch, MagicMock
import sqlite3
from io import BytesIO
import os
import segno
import re

# Import the functions to test
from app import (
    init_db, insert_or_update_patient, get_patient_by_id, create_qr_code, validate_nin, validate_phone,
    connect_to_google_sheet, update_google_sheet_from_db
)


class TestEmergencyMedicalApp(unittest.TestCase):

    @patch("sqlite3.connect")
    def test_init_db(self, mock_connect):
        """
        Test database initialization.
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        init_db()

        # Ensure database connection and query execution
        mock_conn.cursor.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("sqlite3.connect")
    def test_insert_new_patient(self, mock_connect):
        """
        Test inserting a new patient into the database.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate no existing patient (SELECT returns None)
        mock_cursor.fetchone.return_value = None

        # Call function
        insert_or_update_patient(
            "John Doe", 30, "12345678901", "+2348012345678", "John's Contact", "AA", "A+", "Peanuts", "Asthma", "PAT1234", None, None
        )

        # Check that a SELECT query is made to check for duplicates
        mock_cursor.execute.assert_any_call(
            'SELECT uuid, qr_link FROM patients WHERE nin = ? OR phone = ?', ('12345678901', '+2348012345678'))

        # Check that INSERT is called when patient doesn't exist
        mock_cursor.execute.assert_any_call('''
            INSERT INTO patients (uuid, name, age, nin, phone, emergency_contact, genotype, blood_type, allergies, medical_history, patient_id, qr_link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (unittest.mock.ANY, 'John Doe', 30, '12345678901', '+2348012345678', "John's Contact", 'AA', 'A+', 'Peanuts', 'Asthma', 'PAT1234', unittest.mock.ANY))

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("sqlite3.connect")
    def test_update_existing_patient(self, mock_connect):
        """
        Test updating an existing patient in the database.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate existing patient data
        mock_cursor.fetchone.return_value = ('uuid', 'existing_qr_link')

        # Call function
        insert_or_update_patient(
            "John Doe", 31, "12345678901", "+2348012345678", "John's Contact", "AA", "A+", "Dust", "Diabetes", "PAT1234", None, None
        )

        # Check that a SELECT query is made to check for duplicates
        mock_cursor.execute.assert_any_call(
            'SELECT uuid, qr_link FROM patients WHERE nin = ? OR phone = ?', ('12345678901', '+2348012345678'))

        # Check that UPDATE is called when patient exists
        mock_cursor.execute.assert_any_call('''
            UPDATE patients SET name = ?, age = ?, allergies = ?, medical_history = ?, emergency_contact = ?, genotype = ?, blood_type = ?, qr_link = ?
            WHERE nin = ? OR phone = ?
        ''', ('John Doe', 31, 'Dust', 'Diabetes', "John's Contact", 'AA', 'A+', unittest.mock.ANY, '12345678901', '+2348012345678'))

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("sqlite3.connect")
    def test_get_patient_by_id(self, mock_connect):
        """
        Test fetching a patient's information by patient ID.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate fetching patient data
        mock_cursor.fetchone.return_value = ("John Doe", 30, "12345678901", "+2348012345678")

        # Call function
        patient = get_patient_by_id("PAT1234")

        # Ensure correct query was executed
        mock_cursor.execute.assert_called_with(
            'SELECT * FROM patients WHERE patient_id = ?', ('PAT1234',)
        )

        # Validate return value
        self.assertEqual(patient, ("John Doe", 30, "12345678901", "+2348012345678"))

    @patch("os.makedirs")
    @patch("segno.make")
    def test_create_qr_code(self, mock_segno_make, mock_makedirs):
        """
        Test QR code generation and saving it as a file.
        """
        mock_qr = MagicMock()
        mock_segno_make.return_value = mock_qr
        data = "https://example.com"
        file_path = "QR_Codes/test_patient.png"

        # Call the function
        byte_stream = create_qr_code(data, file_path)

        # Ensure directory creation
        mock_makedirs.assert_called_once_with("QR_Codes", exist_ok=True)

        # Ensure QR code was generated and saved
        mock_qr.save.assert_called_once_with(file_path, scale=10)

        # Check that a BytesIO object is returned
        self.assertIsInstance(byte_stream, BytesIO)

    def test_validate_nin(self):
        """
        Test NIN validation.
        """
        valid_nin = "12345678901"
        invalid_nin_short = "12345"
        invalid_nin_non_digit = "12345abcde1"

        self.assertTrue(validate_nin(valid_nin))
        self.assertFalse(validate_nin(invalid_nin_short))
        self.assertFalse(validate_nin(invalid_nin_non_digit))

    def test_validate_phone(self):
        """
        Test phone number validation and formatting.
        """
        valid_phone_10_digits = "08012345678"
        valid_phone_11_digits = "+2348012345678"
        invalid_phone_short = "8012345"

        # Test for valid 10-digit phone number (format should be +234xxxxxxxxxx)
        self.assertEqual(validate_phone(valid_phone_10_digits), "+2348012345678")

        # Test for valid +234-prefixed phone number
        self.assertEqual(validate_phone(valid_phone_11_digits), "+2348012345678")

        # Test for invalid short phone number
        self.assertIsNone(validate_phone(invalid_phone_short))

    @patch("gspread.authorize")
    def test_connect_to_google_sheet(self, mock_authorize):
        """
        Test connecting to a Google Sheet using service account credentials.
        """
        mock_client = MagicMock()
        mock_authorize.return_value = mock_client

        # Simulate fetching a worksheet
        mock_sheet = MagicMock()
        mock_client.open_by_key.return_value = mock_sheet
        mock_worksheet = MagicMock()
        mock_sheet.worksheet.return_value = mock_worksheet

        sheet_id = "1iHn_DTxolFxlTp7Lu25KoKDwdxqb352KLEu4DF04yiE"
        sheet_name = "patients"

        worksheet = connect_to_google_sheet(sheet_id, sheet_name)

        # Check that the Google Sheet is opened by key and worksheet by name
        mock_client.open_by_key.assert_called_once_with(sheet_id)
        mock_sheet.worksheet.assert_called_once_with(sheet_name)

        # Ensure that the correct worksheet is returned
        self.assertEqual(worksheet, mock_worksheet)

    @patch("gspread.authorize")
    @patch("sqlite3.connect")
    def test_update_google_sheet_with_new_record(self, mock_connect, mock_authorize):
        """
        Test updating Google Sheets with new records from SQLite.
        """
        # Mocking SQLite and Google Sheets
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("John Doe", 30, "12345678901", "+2348012345678")]

        mock_worksheet = MagicMock()

        # Simulate a DataFrame fetch query
        query = "SELECT * FROM patients"

        # Call the function to update the Google Sheet
        update_google_sheet_from_db(mock_worksheet, query)

        # Check that the worksheet.clear() was called to clear old data
        mock_worksheet.clear.assert_called_once()

        # Ensure that update is called with correct data
        mock_worksheet.update.assert_called_once()

    @patch("gspread.authorize")
    @patch("sqlite3.connect")
    def test_update_google_sheet_with_old_records(self, mock_connect, mock_authorize):
        """
        Test updating Google Sheets when there are already existing records.
        """
        # Mocking SQLite and Google Sheets
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("Jane Doe", 29, "23456789012", "+2348012345679"),
            ("John Doe", 31, "12345678901", "+2348012345678")
        ]

        mock_worksheet = MagicMock()

        # Simulate a DataFrame fetch query
        query = "SELECT * FROM patients"

        # Call the function to update the Google Sheet
        update_google_sheet_from_db(mock_worksheet, query)

        # Check that the worksheet.clear() was called to clear old data
        mock_worksheet.clear.assert_called_once()

        # Ensure that update is called with correct data for multiple records
        mock_worksheet.update.assert_called_once()

        # Validate the data format sent to the Google Sheet
        sheet_data = [
            ["Jane Doe", 29, "23456789012", "+2348012345679"],
            ["John Doe", 31, "12345678901", "+2348012345678"]
        ]
        self.assertEqual(mock_worksheet.update.call_args[0][1][1:], sheet_data)


if __name__ == '__main__':
    unittest.main()
