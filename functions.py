import sqlite3
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import segno
from io import BytesIO
import os
import uuid
import time
import re


SHEET_ID = st.secrets.google_sheet_credentials.SHEET_ID


# --------------------------
# Database Initialization
# --------------------------


def init_db():
    try:
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                name TEXT,
                age INTEGER,
                nin TEXT UNIQUE,
                phone TEXT UNIQUE,
                emergency_contact TEXT,
                genotype TEXT,
                blood_type TEXT,
                allergies TEXT,
                medical_history TEXT,
                patient_id TEXT UNIQUE,
                qr_link TEXT
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS scan_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_uuid TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_uuid) REFERENCES patients(uuid)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT
            )
        ''')

        conn.commit()
        #st.success("Database initialized successfully.")

    except sqlite3.Error as e:
        log_event("ERROR", f"An error occurred during database initialization: {e}")
    finally:
        if conn:
            conn.close()


# --------------------------
# Logging Events Functions
# --------------------------


def log_event(level: str, message: str):
    try:
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()

        c.execute('''
            INSERT INTO logs (level, message) 
            VALUES (?, ?)
        ''', (level, message))

        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Failed to log event to the database: {e}")
    finally:
        if conn:
            conn.close()

    try:
        logs_worksheet = connect_to_google_sheet(SHEET_ID, 'Logs')
        fetch_and_update_logs(logs_worksheet)
    except Exception as e:
        st.error(f"Failed to log event to Google Sheets: {e}")


def fetch_and_update_logs(worksheet):
    query = "SELECT * FROM logs"
    logs_df = fetch_db_data(query)

    if logs_df is not None and not logs_df.empty:
        sheet_data = [logs_df.columns.values.tolist()] + logs_df.values.tolist()
        worksheet.clear()
        worksheet.update('A1', sheet_data)


# --------------------------
# Connect to Google Sheets
# --------------------------


def connect_to_google_sheet(sheet_id, sheet_name):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('mainCredentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.worksheet(sheet_name)
        #st.success(f"Successfully connected to the Google Sheet: {sheet_name}")
        return worksheet
    except FileNotFoundError:
        st.error("Credentials file not found. Please ensure 'mainCredentials.json' is in the correct directory.")
        return None
    except gspread.SpreadsheetNotFound:
        st.error(f"Google Sheet with ID {sheet_id} not found.")
        return None
    except gspread.WorksheetNotFound:
        st.error(f"Worksheet named {sheet_name} not found in the Google Sheet.")
        return None
    except Exception as e:
        st.error(f"An error occurred while connecting to the Google Sheet: {e}")
        return None


# --------------------------
# Update Google Sheet
# --------------------------

def update_google_sheet_from_db(worksheet, query):
    """
    Fetches data from SQLite and updates the Google Sheet.
    Handles errors using try-except blocks to ensure robustness.

    :param worksheet: The worksheet object from gspread.
    :param query: SQL query to fetch data.
    """
    try:
        # Fetch data from the SQLite DB using the fetch_db_data function
        df = fetch_db_data(query)

        # Check if DataFrame is valid
        if df is None or df.empty:
            st.error("No data available to update the Google Sheet.")
            return

        # Convert DataFrame to a list of lists (for Google Sheets API)
        sheet_data = [df.columns.values.tolist()] + df.values.tolist()

        # Clear existing data in the sheet
        worksheet.clear()

        # Update the Google Sheet with the new data
        worksheet.update('A1', sheet_data)
        st.success("Google Sheet updated successfully with new data.")

    except gspread.exceptions.APIError as e:
        # Handle specific Google Sheets API errors
        st.error(f"Google Sheets API error: {e}")
        return

    except Exception as e:
        # Handle any other unforeseen exceptions
        st.error(
            f"An unexpected error occurred while updating the Google Sheet: {e}")
        return


# --------------------------
# Fetch Data from SQLite
# --------------------------


def fetch_db_data(query):
    try:
        conn = sqlite3.connect('patients.db')
        df = pd.read_sql_query(query, conn)
        st.success("Data fetched successfully from the database.")
        return df
    except sqlite3.Error as e:
        st.error(f"An error occurred while fetching data from the database: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None
    finally:
        if conn:
            conn.close()


# --------------------------
# Log Scan Activities without IP Address
# --------------------------

def log_scan_activity(patient_uuid, scan_worksheet):
    """
    Log the scan activity in the 'scan_activities' table without storing the IP address.
    After logging, sync the scan activities with Google Sheets.
    Handles errors using try-except blocks to ensure robustness.

    :param patient_uuid: The UUID of the patient whose scan activity is being logged.
    :param scan_worksheet: The worksheet object from gspread for logging scan activities.
    """
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()

        # Insert scan activity into the 'scan_activities' table
        c.execute('''
            INSERT INTO scan_activities (patient_uuid)
            VALUES (?)
        ''', (patient_uuid,))

        # Commit the transaction
        conn.commit()

        st.success("Scan activity logged successfully.")

    except sqlite3.Error as e:
        # Handle SQLite database errors
        st.error(f"An error occurred while logging scan activity: {e}")
        return

    except Exception as e:
        # Handle any other unforeseen exceptions
        st.error(f"An unexpected error occurred: {e}")
        return

    finally:
        # Ensure the database connection is closed
        if conn:
            conn.close()

    # Sync the updated scan activities with Google Sheets
    try:
        update_google_sheet_from_db(
            scan_worksheet, "SELECT * FROM scan_activities")
        st.success("Google Sheet updated with scan activities.")

    except Exception as e:
        # Handle errors while updating the Google Sheet
        st.error(
            f"An error occurred while updating the Google Sheet with scan activities: {e}")


# --------------------------
# QR Code Generation (First Time Only) with Download Option
# --------------------------


def create_qr_code(data: str, file_path: str) -> BytesIO:
    try:
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError as e:
        st.error(f"An error occurred while creating the directory: {e}")
        return None

    try:
        qr_code = segno.make(data, error='h')
        qr_code.save(file_path, scale=10)
        st.success(f"QR code saved successfully at {file_path}")

        byte_stream = BytesIO()
        qr_code.save(byte_stream, kind='png', scale=10)
        byte_stream.seek(0)
        return byte_stream
    except Exception as e:
        st.error(f"An error occurred while creating the QR code: {e}")
        return None


# --------------------------
# Validate phone number and emergency contact to ensure both are not the same
# --------------------------


def validate_phone_and_emergency_contact(phone, emergency_contact):
    if phone == emergency_contact:
        st.error("Patient's phone number and emergency contact number cannot be the same.")
        return False
    return True


def validate_nin(nin_value):
    return len(nin_value) == 11 and nin_value.isdigit()


def validate_phone(phone_value):
    phone_digits = re.sub(r'\D', '', phone_value)
    if len(phone_digits) == 10:
        return f"+234{phone_digits}"
    if len(phone_digits) == 11 and phone_digits.startswith("0"):
        return f"+234{phone_digits[1:]}"
    if len(phone_digits) == 13 and phone_digits.startswith("234"):
        return f"+{phone_digits}"
    return None


def validate_emergency_contact(emergency_contact_value):
    contact_digits = re.sub(r'\D', '', emergency_contact_value)
    if len(contact_digits) == 10:
        return f"+234{contact_digits}"
    if len(contact_digits) == 11 and contact_digits.startswith("0"):
        return f"+234{contact_digits[1:]}"
    if len(contact_digits) == 13 and contact_digits.startswith("234"):
        return f"+{contact_digits}"
    return None


# --------------------------
# Fetch Patient Information by ID
# --------------------------


def get_patient_by_id(patient_id):
    try:
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()
        c.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
        patient = c.fetchone()
        if patient is None:
            st.warning(f"No patient found with patient ID: {patient_id}")
            return None
        #st.success(f"Patient found: {patient[2]}")
        return patient
    except sqlite3.Error as e:
        st.error(f"An error occurred while retrieving the patient data: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None
    finally:
        if conn:
            conn.close()


# --------------------------
# Insert or Update Patient Data Based on NIN or Phone
# --------------------------


def insert_or_update_patient(name, age, nin, phone, emergency_contact, genotype, blood_type, new_allergies,
                             new_medical_history, patient_id, patient_worksheet, _scan_worksheet):
    try:
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()

        c.execute('SELECT uuid, qr_link FROM patients WHERE nin = ? OR phone = ?', (nin, phone))
        existing_data = c.fetchone()

        def dedupe_and_clean(text):
            if text:
                return ','.join(sorted(set([entry.strip() for entry in text.split(',') if entry.strip()])))
            return ""

        qr_link = f"https://frequently-beloved-robin.ngrok-free.app/?patient_id={patient_id}"

        if existing_data:
            c.execute('''
                UPDATE patients 
                SET name = ?, age = ?, allergies = ?, medical_history = ?, emergency_contact = ?, genotype = ?, blood_type = ?, qr_link = ?
                WHERE nin = ? OR phone = ?
            ''', (name, age, new_allergies, new_medical_history, emergency_contact, genotype, blood_type, qr_link, nin, phone))
            st.success(f"Patient with the phone number {phone} updated successfully.")
            log_event("INFO", f"Patient with the phone number {phone} updated successfully.")
        else:
            patient_uuid = str(uuid.uuid4())
            new_allergies_cleaned = dedupe_and_clean(new_allergies)
            new_medical_history_cleaned = dedupe_and_clean(new_medical_history)
            c.execute('''
                INSERT INTO patients (uuid, name, age, nin, phone, emergency_contact, genotype, blood_type, allergies, medical_history, patient_id, qr_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (patient_uuid, name, age, nin, phone, emergency_contact, genotype, blood_type, new_allergies_cleaned, new_medical_history_cleaned, patient_id, qr_link))
            st.success(f"New patient with the phone number {phone} added successfully.")
            log_event("INFO", f"New patient with the phone number {phone} added successfully.")

        conn.commit()
    except sqlite3.Error as e:
        st.error(f"An error occurred while inserting/updating the patient record: {e}")
        log_event("ERROR", f"SQLite error while inserting/updating patient: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        log_event("ERROR", f"Unexpected error: {e}")
        return None
    finally:
        if conn:
            conn.close()

    try:
        update_google_sheet_from_db(patient_worksheet, "SELECT * FROM patients")
        st.success("Google Sheet updated successfully with patient data.")
        log_event("INFO", "Google Sheet updated with patient data.")
    except Exception as e:
        st.error(f"An error occurred while updating the Google Sheet: {e}")
        log_event("ERROR", f"Error updating Google Sheet: {e}")
        return None

    return qr_link


def display_first_aid_guide_auto_scroll_with_manual():
    guide_container = st.container()

    guide_sections = [
        """
        **FIRST AID ALERT!**

        **First Aid for Breathing Emergencies**
        - Asthma Attacks: Help the person use their inhaler or find one, calm them, and seek help if the condition worsens.

        **First Aid for Seizures**
        - Ensure the person's safety by clearing the area, and checking that there is no fire or harmful object the person can roll on to.
        - Avoid restraining them and waiting for the seizure to end.
        - Turn the person on their side after the seizure to prevent choking.
        - Call emergency services 112 - Nigeria toll-free number.
        """,
        """
        **First Aid for Eye Injuries (Tear gas or harmful chemicals in the Eyes)**
        - Flush the eye with clean water for chemical exposure.
        - Cover the eye with a sterile dressing in case it’s a physical trauma and seek professional help.
        """,
        """
        **WHEN TO GIVE CPR**

        - **Cardiac Arrest**: If the heart stops beating or beats irregularly, causing the person to collapse, become unresponsive, and stop breathing.
        - **Drowning**: When someone is pulled out of water and is unresponsive and not breathing.
        - **Severe Injury or Trauma**: Following a severe injury, such as a car accident or a fall, if the person is unresponsive and not breathing or gasping.
        - **Drug Overdose**: If someone has overdosed on drugs and is not breathing or has stopped breathing.
        - **Choking**: If the person becomes unresponsive due to choking and stops breathing.
        - **Electrical Shock**: Following electrocution, if the person is unresponsive and not breathing.
        In all cases, call emergency services immediately before or while performing CPR. If you’re trained in CPR, begin with chest compressions and, if possible, give rescue breaths. If you're not trained, stick to chest compressions until help arrives.
        """,
        """
        **STEPS TO GIVE CPR**

        1. **Ensure the Scene is Safe**
            - Before you approach the person, ensure that the environment is safe for both you and the victim. Move yourself and the person from the road or anywhere there is harm before proceeding.

        2. **Check for Responsiveness**
            - Gently shake the person and shout, "Are you okay?", “Call their name repeatedly”
            - If there's no response, proceed to the next step.

        3. **Call for Help**
            - Call emergency services immediately (112 - Nigeria toll-free number or the emergency number in your region).
            - If you're with someone, ask them to call for help in finding an ambulance or a means to convey the person to the hospital.

        4. **Check Breathing**
            - Look for normal breathing (gasping or irregular breathing is not normal).
            - If the person is not breathing or only gasping, begin CPR.
        """,
        """
        5. **Begin Chest Compressions**
            - **Position your hands**: Place the heel of one hand in the centre of the chest (on the lower half of the breastbone), and place your other hand on top, interlocking your fingers.
            - **Body position**: Position yourself with your shoulders directly over your hands and keep your arms straight.
            - **Compress the chest**: Push hard and fast, pressing down at least 2 inches deep (5 cm) at a rate of 100 to 120 compressions per minute.
            - Allow the chest to rise fully between compressions.

        6. **Give Rescue Breaths (If Trained)**
            - Tilt the head back and lift the chin to open the airway.
            - Check that the airway is free and there is no food or anything blocking the airway. If there is, remove it.
            - Pinch the nose closed, cover the person's mouth with yours, and give 2 breaths. Each breath should last about 1 second and make the chest rise.
            - After 2 breaths, return to chest compressions.
            - If you’re not trained, continue chest compressions without rescue breaths.
        """,
        """
        7. **Continue CPR**
            - Continue the cycle of 30 chest compressions and 2 rescue breaths until emergency responders arrive or the person starts to show signs of life, like breathing normally.

        **Important Points**:
        - If you're not trained or unsure about giving breaths, performing continuous chest compressions ("hands-only CPR") is still highly effective.
        - Use firm pressure for compressions, but be cautious with young children or infants, using two fingers for compressions and being gentler than with an adult.

        **Proper CPR can help save a life in the event of cardiac arrest until professional help arrives.**
        """
    ]

    with guide_container:
        for section in guide_sections:
            st.markdown(section)
            time.sleep(3)
