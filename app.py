import streamlit as st
import re
from functions import init_db, display_first_aid_guide_auto_scroll_with_manual, connect_to_google_sheet, log_scan_activity, create_qr_code, get_patient_by_id, insert_or_update_patient
import warnings
from PIL import Image

warnings.filterwarnings("ignore")

# Set page configuration
st.set_page_config(
    page_title="Emergency Medical Information System", layout="wide")

SHEET_ID = st.secrets.google_sheet_credentials.SHEET_ID

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
        # Create columns for layout: patient info on the left, image on the right
        col1, col2 = st.columns([2, 1])  # 2/3 width for patient info, 1/3 for image

        # Column 1: Display patient information
        with col1:
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
            st.markdown('\n'.join(f"- {entry.strip()}" for entry in allergy_entries if entry.strip()))

            # Handle cases where medical history is None
            medical_history = patient[10] if patient[10] is not None else ""

            # Display the medical history as a list
            st.write("**Medical History:**")
            medical_history_entries = medical_history.split(',')
            st.markdown('\n'.join(f"- {entry.strip()}" for entry in medical_history_entries if entry.strip()))

            # Log the scan activity without IP
            log_scan_activity(patient[1], scan_worksheet)  # patient_uuid

            # Display the first aid guide with auto-scroll and manual control
            display_first_aid_guide_auto_scroll_with_manual()

        # Column 2: Display the image
        with col2:
            image_path = 'Heart Compression.png'  # Path to the uploaded image
            image = Image.open(image_path)  # Load the image
            st.image(image, caption="First Aid in Action", use_column_width=True)  # Display the image with caption

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
                        qr_link, f"QR Codes/{name}_{patient_id}.png")

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
