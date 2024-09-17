import streamlit as st
import sqlite3
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import segno
from io import BytesIO
import os
import uuid
import time

# --------------------------
# Database Initialization
# --------------------------

def init_db():
    """
    Initialize the SQLite database, create the 'patients' and 'scan_activities' tables if they don't already exist.
    """
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()

    # Create patients' table with UUID and QR code path
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
            qr_link TEXT  -- Store QR link in the database
        )
    ''')

    # Create a table to log scan activities (without IP address)
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_uuid TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_uuid) REFERENCES patients(uuid)
        )
    ''')

    conn.commit()
    conn.close()


# --------------------------
# Connect to Google Sheets
# --------------------------

def connect_to_google_sheet(sheet_id, sheet_name):
    """
    Connects to a Google Sheet using the service account credentials from the 'credentials.json' file.
    :param sheet_id: The ID of the Google Sheet document.
    :param sheet_name: The specific sheet name to use within the document.
    :return: A worksheet object from gspread.
    """
    # Define the scope for accessing Google Sheets and Google Drive
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    # Load credentials from the service account JSON file
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        'mainCredentials.json', scope)

    # Authorize the client
    client = gspread.authorize(creds)

    # Get the sheet by ID and worksheet by name
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(sheet_name)

    return worksheet


# --------------------------
# Fetch Data from SQLite
# --------------------------

def fetch_db_data(query):
    """
    Fetches data from the SQLite database and returns it as a pandas DataFrame.
    :param query: SQL query to fetch data.
    :return: DataFrame with fetched data.
    """
    conn = sqlite3.connect('patients.db')
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# --------------------------
# Update Google Sheet
# --------------------------

def update_google_sheet_from_db(worksheet, query):
    """
    Fetches data from SQLite and updates the Google Sheet.
    :param worksheet: The worksheet object from gspread.
    :param query: SQL query to fetch data.
    """
    # Fetch data from the SQLite DB
    df = fetch_db_data(query)

    # Convert DataFrame to a list of lists (for Google Sheets API)
    sheet_data = [df.columns.values.tolist()] + df.values.tolist()

    # Clear existing data in the sheet
    worksheet.clear()

    # Update the Google Sheet with the new data
    worksheet.update('A1', sheet_data)  # Assuming data starts from A1


# --------------------------
# Log Scan Activities without IP Address
# --------------------------

def log_scan_activity(patient_uuid, scan_worksheet):
    """
    Log the scan activity in the scan_activities table without storing IP address.
    After logging, sync with Google Sheets.
    """
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()

    c.execute('''
        INSERT INTO scan_activities (patient_uuid)
        VALUES (?)
    ''', (patient_uuid,))

    conn.commit()
    conn.close()

    # Update the Google Sheet for scan activities
    update_google_sheet_from_db(
        scan_worksheet, "SELECT * FROM scan_activities")


# --------------------------
# QR Code Generation (First Time Only) with Download Option
# --------------------------

def create_qr_code(data: str, file_path: str) -> BytesIO:
    """
    Generate a QR code with the specified data (e.g., the patient ID URL) and save it as a PNG file.
    Returns the image as a BytesIO object for download.
    """
    # Ensure the directory exists
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Generate the QR code
    # 'h' sets a high error correction level
    qr_code = segno.make(data, error='h')

    # Save the QR code with an appropriate scale factor (e.g., scale=10 for moderately large QR codes)
    qr_code.save(file_path, scale=10)

    # Create a BytesIO stream to enable downloading
    byte_stream = BytesIO()
    qr_code.save(byte_stream, kind='png', scale=10)
    byte_stream.seek(0)
    return byte_stream


# --------------------------
# Fetch Patient Information by ID
# --------------------------

def get_patient_by_id(patient_id):
    """
    Retrieve a patient's information using their unique ID from the database.
    """
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()
    c.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
    patient = c.fetchone()
    conn.close()
    return patient


# --------------------------
# Insert or Update Patient Data Based on NIN or Phone
# --------------------------


def insert_or_update_patient(name, age, nin, phone, emergency_contact, genotype, blood_type, new_allergies,
                             new_medical_history, patient_id, patient_worksheet, scan_worksheet):
    """
    Insert a new patient into the database or update an existing patient’s record.
    After updating, sync with Google Sheets.
    Store the QR link in the database and generate a QR code based on the link.
    """
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()

    # Check if the patient already exists by NIN or Phone
    c.execute(
        'SELECT uuid, qr_link FROM patients WHERE nin = ? OR phone = ?', (nin, phone))
    existing_data = c.fetchone()

    # Helper function to deduplicate and clean entries
    def dedupe_and_clean(text):
        if text:
            return ','.join(sorted(set([entry.strip() for entry in text.split(',') if entry.strip()])))
        return ""

    # Generate a persistent QR link based on the patient ID
    qr_link = f"https://frequently-beloved-robin.ngrok-free.app/?patient_id={patient_id}"

    if existing_data:
        # Patient exists, update the record, reuse the existing QR link
        c.execute('''
            UPDATE patients 
            SET name = ?, age = ?, allergies = ?, medical_history = ?, emergency_contact = ?, genotype = ?, blood_type = ?, qr_link = ?
            WHERE nin = ? OR phone = ?
        ''', (name, age, new_allergies, new_medical_history, emergency_contact, genotype, blood_type, qr_link, nin, phone))

        st.success(
            f"Patient with the NIN {nin} or phone number {phone} updated successfully.")

    else:
        # New patient, insert the record with a generated UUID and store the QR link
        patient_uuid = str(uuid.uuid4())  # Generate a unique UUID
        new_allergies_cleaned = dedupe_and_clean(new_allergies)
        new_medical_history_cleaned = dedupe_and_clean(new_medical_history)

        c.execute('''
            INSERT INTO patients (uuid, name, age, nin, phone, emergency_contact, genotype, blood_type, allergies, medical_history, patient_id, qr_link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (patient_uuid, name, age, nin, phone, emergency_contact, genotype, blood_type, new_allergies_cleaned,
              new_medical_history_cleaned, patient_id, qr_link))

        st.success(
            f"New patient with the NIN {nin} and phone number {phone} added successfully.")

    conn.commit()
    conn.close()

    # Sync the updated patient data with Google Sheets
    update_google_sheet_from_db(patient_worksheet, "SELECT * FROM patients")

    # Generate and return the QR code image based on the qr_link
    return qr_link


def display_first_aid_guide_auto_scroll_with_manual():
    # Create a scrollable container that the user can manually scroll
    guide_container = st.container()

    # Full guide content split into chunks for auto-scroll simulation
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

    # Simulate auto-scroll by adding content incrementally within the scrollable container
    with guide_container:
        for section in guide_sections:
            st.markdown(section)
            time.sleep(3)  # Simulate delay before showing the next section