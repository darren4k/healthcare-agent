"""Mock EMR Flask Application for testing browser automation."""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
import secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Mock data
MOCK_USERS = {
    "demo_therapist": {"password": "demo123", "name": "Jane Smith, PT"},
    "admin": {"password": "admin123", "name": "Admin User"}
}

MOCK_PATIENTS = {
    "PT-12345": {"first_name": "John", "last_name": "Doe", "dob": "1965-05-15"},
    "PT-67890": {"first_name": "Mary", "last_name": "Johnson", "dob": "1972-08-22"},
    "OT-11111": {"first_name": "Alice", "last_name": "Williams", "dob": "1958-03-12"}
}

# Store submitted notes (in-memory)
SOAP_NOTES = []


def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Home page - redirects to login or dashboard."""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in MOCK_USERS and MOCK_USERS[username]['password'] == password:
            session['username'] = username
            session['name'] = MOCK_USERS[username]['name']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout."""
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard."""
    return render_template('dashboard.html',
                         username=session.get('name'),
                         patients=MOCK_PATIENTS)


@app.route('/patients')
@login_required
def patients():
    """Patient list page."""
    search_query = request.args.get('search', '').upper()

    if search_query:
        filtered_patients = {
            pid: info for pid, info in MOCK_PATIENTS.items()
            if search_query in pid or
               search_query in info['first_name'].upper() or
               search_query in info['last_name'].upper()
        }
    else:
        filtered_patients = MOCK_PATIENTS

    return render_template('patients.html', patients=filtered_patients, search_query=search_query)


@app.route('/patients/<patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail page."""
    if patient_id not in MOCK_PATIENTS:
        return "Patient not found", 404

    patient = MOCK_PATIENTS[patient_id]
    # Get patient's notes
    patient_notes = [note for note in SOAP_NOTES if note['patient_id'] == patient_id]

    return render_template('patient_detail.html',
                         patient_id=patient_id,
                         patient=patient,
                         notes=patient_notes)


@app.route('/patients/<patient_id>/notes/new', methods=['GET', 'POST'])
@login_required
def new_note(patient_id):
    """Create new SOAP note."""
    if patient_id not in MOCK_PATIENTS:
        return "Patient not found", 404

    if request.method == 'POST':
        note = {
            'patient_id': patient_id,
            'subjective': request.form.get('subjective'),
            'objective': request.form.get('objective'),
            'assessment': request.form.get('assessment'),
            'plan': request.form.get('plan'),
            'visit_date': request.form.get('visit_date'),
            'visit_type': request.form.get('visit_type'),
            'created_by': session.get('name'),
            'created_at': datetime.now().isoformat(),
            'status': request.form.get('action', 'draft')  # 'draft' or 'final'
        }

        SOAP_NOTES.append(note)

        return render_template('note_success.html',
                             patient_id=patient_id,
                             note=note)

    patient = MOCK_PATIENTS[patient_id]
    return render_template('new_note.html',
                         patient_id=patient_id,
                         patient=patient,
                         today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/api/notes', methods=['GET'])
def api_notes():
    """API endpoint to get all notes."""
    return jsonify(SOAP_NOTES)


@app.route('/api/patients/<patient_id>/notes', methods=['GET'])
def api_patient_notes(patient_id):
    """API endpoint to get patient's notes."""
    patient_notes = [note for note in SOAP_NOTES if note['patient_id'] == patient_id]
    return jsonify(patient_notes)


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏥 Mock EMR System Starting...")
    print("="*60)
    print("\n📋 Login Credentials:")
    print("   Username: demo_therapist")
    print("   Password: demo123")
    print("\n🔗 Access at: http://localhost:5000")
    print("="*60 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
