import streamlit as st
import sqlite3
import segno
from io import BytesIO
import os
import pandas as pd
import re
import uuid
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# Google Sheet ID for VisionX document
SHEET_ID = '1iHn_DTxolFxlTp7Lu25KoKDwdxqb352KLEu4DF04yiE'

# Set page configuration
st.set_page_config(
    page_title="Emergency Medical Information System", layout="wide")


# ----------


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
# CPR Instructions Display
# --------------------------

def display_cpr_guide():
    """
    Display a step-by-step guide for administering CPR in an emergency.
    """
    st.subheader("CPR Instructions")
    st.write("""
    **1. Ensure the scene is safe.**

    **2. Tap the person and shout, 'Are you okay?'**

    **3. Call 911 or ask someone else to do so.**

    **4. Begin chest compressions.**
        - Push hard and fast in the center of the chest, about 2 inches deep, at a rate of 100-120 compressions per minute.

    **5. Continue until help arrives or the person starts to breathe.**

    """)


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


# --------------------------
# Helper Functions
# --------------------------


def validate_nin(nin):
    return len(nin) == 11 and nin.isdigit()


def validate_phone(phone):
    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) == 10:
        return f"+234{phone_digits}"
    if len(phone_digits) == 11 and phone_digits.startswith("0"):
        return f"+234{phone_digits[1:]}"
    if len(phone_digits) == 13 and phone_digits.startswith("234"):
        return f"+{phone_digits}"
    return None


def validate_emergency_contact(contact):
    contact_digits = re.sub(r'\D', '', contact)
    if len(contact_digits) == 10:
        return f"+234{contact_digits}"
    if len(contact_digits) == 11 and contact_digits.startswith("0"):
        return f"+234{contact_digits[1:]}"
    if len(contact_digits) == 13 and contact_digits.startswith("234"):
        return f"+{contact_digits}"
    return None


# --------------------------
# Main Logic
# --------------------------

# Initialize the SQLite database and create the 'patients' table
init_db()

# Google Sheets setup for "VisionX" Google Sheet with two sheets: 'patients' and 'scan_activities'
patient_worksheet = connect_to_google_sheet(SHEET_ID, 'patients')
scan_worksheet = connect_to_google_sheet(SHEET_ID, 'scan_activities')

# Parse the query parameters from the URL
query_params = st.query_params
# Get the full patient_id directly
patient_id = query_params.get("patient_id", None)

# Check if a patient_id is in the query parameters
if "patient_id" in query_params:

    # Fetch patient information
    patient = get_patient_by_id(patient_id)

    if patient:
        st.subheader(f"Medical Information for {patient[2]}")  # Patient name
        st.write(f"**Age:** {patient[3]}")
        st.write(f"**Phone Number:** {patient[5]}")
        st.write(f"**Emergency Contact:** {patient[6]}")
        st.write(f"**Genotype:** {patient[7]}")
        st.write(f"**Blood Type:** {patient[8]}")

        # Handle case where allergies are None
        allergies = patient[9] if patient[9] is not None else ""

        # Display the allergies as a list
        st.write("**Allergies:**")
        allergy_entries = allergies.split(',')
        st.markdown(
            '\n'.join(f"- {entry.strip()}" for entry in allergy_entries if entry.strip()))

        # Handle cases where medical history is None
        medical_history = patient[10] if patient[10] is not None else ""

        # Display the medical history as a list
        st.write("**Medical History:**")
        medical_history_entries = medical_history.split(',')
        st.markdown(
            '\n'.join(f"- {entry.strip()}" for entry in medical_history_entries if entry.strip()))

        # Log the scan activity without IP
        log_scan_activity(patient[1], scan_worksheet)  # patient_uuid

        # Display the CPR guide after displaying the patient's information
        display_cpr_guide()

    else:
        st.error("There is no medical record for this patient.")
else:
    st.title("Emergency Medical Information System")

    with st.form("patient_form"):
        name = st.text_input("Patient Name")
        age = st.number_input("Patient Age", min_value=0,
                              max_value=120, step=1)
        nin = st.text_input("National Identification Number (NIN)",
                            help="Enter your NIN (exactly 11 digits)")
        phone = st.text_input("Phone Number",
                              help="Enter a valid phone number (10 or 11 digits, will be prefixed with +234)")
        emergency_contact = st.text_input("Emergency Contact Number",
                                          help="Enter a valid phone number for emergency contact")
        genotype = st.selectbox("Genotype", options=["AA", "AC", "AS", "CC", "SS", "SC"],
                                help="Select the patient's genotype")
        blood_type = st.selectbox("Blood Type", options=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                                  help="Select the patient's blood type")
        allergies = st.text_area(
            "Known Allergies (Separate entries with commas)", help="e.g., Penicillin, Peanuts")
        medical_history = st.text_area("Medical History (Separate entries with commas)",
                                       help="e.g., Asthma, Diabetes, Hypertension")

        # Consent clause checkbox
        consent = st.checkbox(
            """I hereby consent to the use and disclosure of my health and biometric information provided to VisionX 
            for purposes including, but not limited to, safety and emergency situations. I understand that in the 
            event of theft, emergency, or any situation where my safety or the safety of others is at risk, 
            this information may be made publicly available or shared with the necessary authorities or individuals 
            to assist in resolving the situation."""
        )

        submitted = st.form_submit_button("Submit")

    if submitted:
        if consent:
            if not validate_nin(nin):
                st.error("NIN must be exactly 11 digits.")
            else:
                phone_number = validate_phone(phone)
                emergency_contact_number = validate_emergency_contact(
                    emergency_contact)

                if not phone_number:
                    st.error("Invalid phone number format.")
                elif not emergency_contact_number:
                    st.error("Invalid emergency contact number format.")
                else:
                    patient_id = f"PAT{nin[-4:]}{age}{phone[-4:]}"

                    # Insert or update patient and get the QR link (URL)
                    qr_link = insert_or_update_patient(
                        name, age, nin, phone_number, emergency_contact_number, genotype, blood_type,
                        allergies, medical_history, patient_id, patient_worksheet, scan_worksheet
                    )

                    # Generate the QR code based on the qr_link
                    qr_code = create_qr_code(
                        qr_link, f"QR_Codes/{name}_{patient_id}.png")

                    # Display the generated QR code
                    st.image(
                        qr_code, caption="Scan this QR code to view medical information", width=300)

                    # Allow users to download the QR code image
                    st.download_button(
                        label="Download QR Code",
                        data=qr_code,
                        file_name=f"{name}_{patient_id}.png",
                        mime="image/png"
                    )

                    # Show the QR URL (always points to the patient’s medical record)
                    st.write(f"QR Code URL: {qr_link}")

        else:
            st.error("You must provide consent to submit the form.")


# the footer and more information
st.markdown(
    """<p style="color:white ; text-align:center;font-size:15px;"> Copyright | VisionX 2024(c) </p>
    """,
    unsafe_allow_html=True,
)
