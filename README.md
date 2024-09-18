# Emergency Medical Information System (EMIS)

[![Docker](https://github.com/Behordeun/VisionX-emis/actions/workflows/build_cicd.yml/badge.svg)](https://github.com/Behordeun/VisionX-emis/actions/workflows/build_cicd.yml/badge.svg)  [![Netlify Status](https://api.netlify.com/api/v1/badges/9b8a94ee-56e7-4d0f-9956-b5f1670f5756/deploy-status)](https://app.netlify.com/sites/visionx-emis/deploys)  [![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FBehordeun%2FVisionX-emis.svg?type=shield&issueType=license)](https://app.fossa.com/projects/git%2Bgithub.com%2FBehordeun%2FVisionX-emis?ref=badge_shield&issueType=license)  [![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FBehordeun%2FVisionX-emis.svg?type=shield&issueType=security)](https://app.fossa.com/projects/git%2Bgithub.com%2FBehordeun%2FVisionX-emis?ref=badge_shield&issueType=security)  [![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FBehordeun%2FVisionX-emis.svg?type=small)](https://app.fossa.com/projects/git%2Bgithub.com%2FBehordeun%2FVisionX-emis?ref=badge_small)

## Table of Contents
1. [Introduction](#introduction)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [Installation](#installation)
5. [Setup and Configuration](#setup-and-configuration)
6. [How to Use](#how-to-use)
7. [Google Sheets Integration](#google-sheets-integration)
8. [Database Structure](#database-structure)
9. [Running Tests](#running-tests)
10. [File Structure](#file-structure)
11. [License](#license)

## Introduction

The **Emergency Medical Information System (EMIS)** is a web-based application that helps medical teams or first responders access a patient's medical information in emergency situations. The system allows users to:
- Store patient medical records.
- Generate a QR code that can be scanned to retrieve the patient’s data.
- Display critical first-aid information and CPR guides.
- Log scan activities, ensuring quick tracking of access history.
- Sync patient and scan activities data with Google Sheets for real-time reporting.

## Features

- **Patient Information Storage**: Store medical data such as allergies, blood type, genotype, and medical history.
- **QR Code Generation**: Generate a scannable QR code for each patient, which links to their medical data.
- **First-Aid and CPR Guide**: Provide crucial first-aid tips and CPR instructions on the patient's profile.
- **Google Sheets Integration**: Sync patient and scan activity data with Google Sheets.
- **Database Logging**: Logs of patient scan activities and system events in a local SQLite database.

## Tech Stack

- **Backend**: Python (with SQLite3 for local storage)
- **Web Framework**: Streamlit
- **Google Sheets API**: To sync patient and scan activities data.
- **QR Code Generation**: Segno library for QR code creation.
- **Database**: SQLite for patient and activity data.
- **Testing**: Unittest with Mocking and patching.

## Installation

To run the application locally, follow the steps below:

1. **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd emergency-medical-information-system
    ```

2. **Install required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Set up the Google Sheets API credentials**:
    - You will need a `credentials.json` file with Google API credentials. Follow the steps in the [Google Sheets API documentation](https://developers.google.com/sheets/api/quickstart/python) to get these credentials.
    - Place the `credentials.json` file in the root directory of the project.

## Setup and Configuration

### Environment Variables

Create a `.streamlit/secrets.toml` file in the project directory to securely store your Google Sheet ID and credentials. Here's an example:

```toml
[google_sheet_credentials]
SHEET_ID = "<your-google-sheet-id>"
```

Make sure to replace `<your-google-sheet-id>` with the actual ID of your Google Sheet document.

### Database Initialization

On the first run, the system will automatically initialize the SQLite database (`patients.db`) with the required tables (`patients`, `scan_activities`, `logs`).

You can customize the database by adding or modifying the structure in the `functions.py` script's `init_db()` method.

## How to Use

1. **Patient Data Entry**:
    - On the home page, a form is provided for adding or updating patient information. Fields include name, age, NIN (National Identification Number), phone number, emergency contact, blood type, genotype, allergies, and medical history.
    - Once submitted, a unique patient ID is generated, and a QR code is created that links to this information.

2. **Viewing Patient Information**:
    - By scanning the generated QR code, the patient's profile can be retrieved, displaying their essential medical details such as allergies, genotype, blood type, and more.

3. **First Aid and CPR Instructions**:
    - Each patient profile includes a built-in guide for first-aid steps and CPR instructions. This guide is scrollable with auto-scroll functionality for easy access during emergencies.

4. **QR Code Generation**:
    - The system will generate a QR code that can be scanned to access the patient’s information. The QR code can also be downloaded and printed for easy use.

5. **Google Sheets Integration**:
    - The system syncs patient information and scans activity logs with Google Sheets, ensuring a backup and easy access for administrators.

## Google Sheets Integration

### Setting Up Google Sheets

1. **Create a Google Sheet**:
   - Go to Google Sheets and create a new sheet.
   - The sheet should have two tabs named `patients` and `scan_activities`.

2. **Configure API Credentials**:
   - Place the `credentials.json` file obtained from the Google Cloud Console in the root directory.
   - In the `.streamlit/secrets.toml` file, ensure the `SHEET_ID` is correctly set for the Google Sheet you're using.

### Syncing Data

- **Patient Data**: Whenever a new patient is added or an existing patient's record is updated, the data is automatically synced with the `patients` tab in Google Sheets.
- **Scan Activity Data**: Every time a QR code is scanned, a log entry is added to the `scan_activities` tab in Google Sheets, tracking the activity.

## Database Structure

### Tables

1. **patients**:
    - `id`: Primary key (auto-incremented).
    - `uuid`: Unique identifier for the patient.
    - `name`: Name of the patient.
    - `age`: Age of the patient.
    - `nin`: National Identification Number (unique).
    - `phone`: Phone number (unique).
    - `emergency_contact`: Emergency contact number.
    - `genotype`: Patient's genotype.
    - `blood_type`: Blood type of the patient.
    - `allergies`: Known allergies.
    - `medical_history`: Medical history.
    - `patient_id`: Unique patient ID.
    - `qr_link`: Link to the QR code for the patient.

2. **scan_activities**:
    - `id`: Primary key (auto-incremented).
    - `patient_uuid`: UUID of the patient whose scan activity is logged.
    - `timestamp`: Time of scan activity.

3. **logs**:
    - `id`: Primary key (auto-incremented).
    - `timestamp`: Log event time.
    - `level`: Severity level (INFO, WARNING, ERROR).
    - `message`: Log message.

## Running Tests

The application comes with unit tests that ensure key functionality works correctly.

### Running Tests

To run the test suite, use the following command:

```bash
python -m unittest discover -s tests
```

The tests include:
- Database initialization and data insertion.
- QR code generation.
- Data validation (phone, NIN, emergency contacts).
- Google Sheets connection and data sync.
- Log event handling.

## File Structure

```plaintext
├── app.py                    # Main application logic
├── functions.py              # Helper functions (database, Google Sheets, QR generation, etc.)
├── tests/
│   ├── test_app.py           # Unit tests for the application
├── requirements.txt          # Python dependencies
├── .streamlit/
│   └── secrets.toml          # Secrets and environment variables
├── LICENSE                   # License file
├── patients.db               # SQLite database (auto-generated)              
└── README.md                 # This file
```

## License

This project is licensed under the MIT-License - see the [LICENSE](LICENSE) file for details.