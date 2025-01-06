import sys
sys.path.append(r'C:\users\kalpe\appData\roaming\python\python312\site-packages')

from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from haversine import haversine, Unit
from pymongo import MongoClient, DESCENDING
from bson import ObjectId
import json
from datetime import datetime, timedelta
import logging
from flask import current_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Add this custom JSON encoder to handle ObjectI


app = Flask(__name__)

# MongoDB setup
client = MongoClient("mongodb+srv://Kalpeshpawar:010420011@cluster0.usfz4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0") 
db = client['attendance_system']
punch_collection = db['punch_records']

# Geofence center and radius
geofence_center = (22.27174507140292, 73.17586006441583)  # Example coordinates
geofence_radius = 1000000  # 1000 meters radius



# Predefined users and their credentials (username, password)
users = {
    "user1": "password1",
    "user2": "password2",
    "user3": "password3",
    "admin": "adminpass" ,
}

logged_in_user = None

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

def get_time_with_offset():
    """Returns the current time with a +5:30 offset (IST)."""
    current_time = datetime.utcnow()  # Get current UTC time
    offset = timedelta(hours=5, minutes=30)  # IST offset
    ist_time = current_time + offset
    return ist_time

def get_user_last_punch(username):
    """Get the last punch record for a specific user"""
    last_punch = punch_collection.find_one(
        {"username": username},
        sort=[("timestamp", -1)]
    )
    
    # Check if last punch was more than 36 hours ago
    if last_punch:
        current_time = get_time_with_offset()
        time_difference = current_time - last_punch['timestamp']
        if time_difference.total_seconds() > (36 * 3600):  # 36 hours in seconds
            return None  # This will reset to Punch In state
    
    return last_punch

def calculate_work_duration(punch_in_time, punch_out_time):
    """Calculate duration between punch in and punch out"""
    if not punch_in_time or not punch_out_time:
        return None
    
    duration = punch_out_time - punch_in_time
    hours = duration.total_seconds() / 3600
    return round(hours, 2)



# Haversine formula to calculate distance
def calculate_distance(user_location):
    return haversine(user_location, geofence_center, unit=Unit.METERS)

# HTML Login Page
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 200px;
            margin: 40px auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        h1, h2 {
            color: #333;
            text-align: center;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
        }
        select, input {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 10px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #45a049;
        }
        .error {
            color: #dc3545;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            text-align: center;
        }
        .success {
            color: #28a745;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            text-align: center;
        }
        .logout {
            text-align: right;
            margin-bottom: 20px;
        }
        .logout-btn {
            background-color: #dc3545;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
        }
        .logout-btn:hover {
            background-color: #c82333;
        }
    </style>

</head>
<body>
    <h2>Login</h2>
    <form method="POST">
        <label for="username">Select Username:</label>
        <select id="username" name="username" required>
            <option value="user1">User 1</option>
            <option value="user2">User 2</option>
            <option value="user3">User 3</option>
            <option value="admin">User 3</option>
        </select><br><br>
        
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" required><br><br>
        
        <button type="submit">Login</button>
    </form>
    {% if error %}
    <p style="color: red;">{{ error }}</p>
    {% endif %}
</body>
</html>
"""
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance Punch System</title>
    <script>
        // Auto-logout after 50 seconds
        setTimeout(function() {
            window.location.href = '/logout'; // Redirect to the logout route
        }, 50000); // 50 seconds in milliseconds

        
    </script>    
    <style>
        .punch-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            font-size: 1.2em;
            font-weight: bold;
            color: #fff;
            cursor: pointer;
            margin: 10px auto;
            line-height: 150px;
            position: relative;
        }
        .punch-in {
            background-color: #4CAF50;
        }
        .punch-out {
            background-color: #f44336;
        }
        .punch-circle:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        #geofence-status {
            margin-top: 20px;
        }
        #punch-history {
            margin-top: 20px;
        }
        #punch-history ul {
            list-style-type: none;
        }
        .remark-section {
            margin-bottom: 20px;
        }
       .remark-input {
            width: 100%;
            padding: 8px;
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        #user-coordinates {
            margin-top: 10px;
            font-weight: bold;
            color: #ff0000;
        }
    </style>
</head>
<body>
    <header>
        <h1>Attendance Punch System</h1>
    </header>

    <main>
        <section id="geofence-status">
            <p>Geofence Status: <span id="geofence-indicator">Checking...</span></p>
            <p id="user-coordinates" style="display: none;">Your Location: <span id="coordinates"></span></p>
        </section>

        <section id="punch-controls">           
            <div id="punch-in" class="punch-circle punch-in" style="display: none;">Punch In</div>
            <div id="punch-out" class="punch-circle punch-out" style="display: none;">Punch Out</div>
            <div class="remark-section">
                <label for="user-remark">Remark (optional):</label>
                <input type="text" id="user-remark" class="remark-input" placeholder="Enter your remark">
            </div>
        </section>    


        <section id="punch-history">
            <h2>Punch History</h2>
            <ul id="history-list">
                <!-- Dynamic Punch History Will Populate Here -->
            </ul>
        </section>
        <form method="POST" action="/logout">
            <button type="submit">Logout</button>
        </form>           
    </main>

    <footer>
        <p>&copy; 2025 Attendance System</p>
    </footer>


    <script>
let hasPunchedIn = {{ 'true' if initial_status == 'Punch In' else 'false' }};
let isProcessing = false;

function updateButtonVisibility() {
    if (hasPunchedIn) {
        document.getElementById('punch-in').style.display = 'none';
        document.getElementById('punch-out').style.display = 'block';
    } else {
        document.getElementById('punch-in').style.display = 'block';
        document.getElementById('punch-out').style.display = 'none';
    }
}

function checkLastPunchStatus() {
    fetch('/last_punch_status')
        .then(response => response.json())
        .then(data => {
            if (data.action) {
                const lastPunchTime = new Date(data.timestamp);
                const currentTime = new Date();
                const hoursDifference = (currentTime - lastPunchTime) / (1000 * 60 * 60);
                hasPunchedIn = hoursDifference <= 36 && (data.action === 'Punch In');
                updateButtonVisibility();
            }
        });
}

function checkGeofenceStatus(position) {
    const userLat = position.coords.latitude;
    const userLng = position.coords.longitude;

    return fetch('/get_geofence_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: userLat, longitude: userLng })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('geofence-indicator').innerText = data.status;

        if (data.status === 'Outside Geofence') {
            document.getElementById('coordinates').innerText = `Lat: ${userLat}, Lng: ${userLng}`;
            document.getElementById('user-coordinates').style.display = 'block';
            document.getElementById('punch-in').style.display = 'none';
            document.getElementById('punch-out').style.display = 'none';
        } else {
            document.getElementById('user-coordinates').style.display = 'none';
            updateButtonVisibility();
        }
    })
    .catch(error => {
        console.error('Geofence Error:', error);
        document.getElementById('geofence-indicator').innerText = 'Error checking location';
    });
}

function requestLocationPermission() {
    if (!navigator.geolocation) {
        document.getElementById('geofence-indicator').innerText = 'Geolocation not supported';
        return;
    }

    const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
    };

    navigator.geolocation.watchPosition(
        checkGeofenceStatus,
        (error) => {
            let message = 'Location error: ';
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    message += 'Please enable location services';
                    break;
                case error.POSITION_UNAVAILABLE:
                    message += 'Location unavailable';
                    break;
                case error.TIMEOUT:
                    message += 'Request timed out';
                    break;
                default:
                    message += 'Unknown error';
            }
            document.getElementById('geofence-indicator').innerText = message;
        },
        options
    );
}

function handlePunchAction(action) {
    if (isProcessing) return;
    
    isProcessing = true;
    showStatusMessage("Processing...");
    disableButtons();

    const userRemark = document.getElementById('user-remark').value;
    
    navigator.geolocation.getCurrentPosition(
        (position) => {
            fetch('/punch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: action,
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    userRemark: userRemark
                })
            })
            .then(response => response.json())
            .then(data => {
                addPunchRecord(data.message);
                hasPunchedIn = (action === 'Punch In');
                updateButtonVisibility();
                showStatusMessage("Saved successfully!");
            })
            .catch(error => {
                console.error('Punch Error:', error);
                showStatusMessage("Error saving punch!");
            })
            .finally(() => {
                setTimeout(() => {
                    isProcessing = false;
                    enableButtons();
                }, 5000);
            });
        },
        (error) => {
            console.error('Location Error:', error);
            showStatusMessage("Location error!");
            isProcessing = false;
            enableButtons();
        }
    );
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkLastPunchStatus();
    requestLocationPermission();
    
    document.getElementById('punch-in').addEventListener('click', () => handlePunchAction('Punch In'));
    document.getElementById('punch-out').addEventListener('click', () => handlePunchAction('Punch Out'));
});

        function addPunchRecord(record) {
            const listItem = document.createElement('li');
            listItem.textContent = record;
            document.getElementById('history-list').insertBefore(listItem, document.getElementById('history-list').firstChild);
        }

        function showStatusMessage(message) {
            const statusElement = document.createElement('p');
            statusElement.id = 'status-message';
            statusElement.textContent = message;
            document.body.appendChild(statusElement);

            setTimeout(() => {
                const existingStatusElement = document.getElementById('status-message');
                if (existingStatusElement) {
                    existingStatusElement.remove();
                }
            }, 5000);
        }

        function disableButtons() {
            document.getElementById('punch-in').disabled = true;
            document.getElementById('punch-out').disabled = true;
        }

        function enableButtons() {
            document.getElementById('punch-in').disabled = false;
            document.getElementById('punch-out').disabled = false;
        }

        // Load punch history on page load
        fetch('/last_punch_status')
            .then(response => response.json())
            .then(data => {
                if (data.action) {
                    addPunchRecord(`Last ${data.action} at ${data.timestamp}`);
                }
            });
    </script>



</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Attendance System</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background-color: white;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        select {
            padding: 6px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 120px;
        }
        .save-btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 20px;
        }
        .save-btn:hover {
            background-color: #45a049;
        }
        .status-pending {
            color: #f0ad4e;
        }
        .status-approved {
            color: #5cb85c;
        }
        .status-rejected {
            color: #d9534f;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .logout-btn {
            background-color: #dc3545;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .filter-section {
            margin-bottom: 20px;
        }
        .filter-section select {
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Admin Dashboard</h1>
            <form method="POST" action="/logout" style="margin: 0;">
                <button type="submit" class="logout-btn">Logout</button>
            </form>
        </div>
        
        <div class="filter-section">
            <select id="userFilter" onchange="filterRecords()">
                <option value="">All Users</option>
                <option value="user1">User 1</option>
                <option value="user2">User 2</option>
                <option value="user3">User 3</option>
            </select>
            <select id="statusFilter" onchange="filterRecords()">
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
            </select>
        </div>

        <table id="attendanceTable">
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Action</th>
                    <th>Date & Time</th>
                    <th>Status</th>
                    <th>Status Changed At</th>
                    <th>Work Duration (Hours)</th>
                    <th>Admin Remark</th>
                </tr>
            </thead>
            <tbody>
                {% for record in records %}
                <tr data-username="{{ record.username }}" data-status="{{ record.status }}">
                    <td>{{ record.username }}</td>
                    <td>{{ record.action }}</td>
                    <td>{{ record.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td>
                    <td>{{ record.userRemark or '' }}</td>
                    <td>
                        <select class="status-select" data-record-id="{{ record._id }}">
                            <option value="pending" {% if record.status == 'pending' %}selected{% endif %}>Pending</option>
                            <option value="approved" {% if record.status == 'approved' %}selected{% endif %}>Approved</option>
                            <option value="rejected" {% if record.status == 'rejected' %}selected{% endif %}>Rejected</option>
                        </select>
                    </td>
                    <td>{{ record.statusChangedAt.strftime('%Y-%m-%d %H:%M:%S') if record.statusChangedAt else '' }}</td>                    
                    <td>{{ record.workDuration if record.workDuration is not none else '' }}</td>
                    <td>
                        <input type="text" class="admin-remark" data-record-id="{{ record._id }}" 
                               value="{{ record.adminRemark or '' }}" placeholder="Add remark">
                    </td>                
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <button onclick="saveChanges()" class="save-btn">Save Changes</button>
    </div>

    <script>
        let changedRecords = new Set();

        function filterRecords() {
            const userFilter = document.getElementById('userFilter').value;
            const statusFilter = document.getElementById('statusFilter').value;
            const rows = document.querySelectorAll('#attendanceTable tbody tr');

            rows.forEach(row => {
                const username = row.getAttribute('data-username');
                const status = row.getAttribute('data-status');
                const userMatch = !userFilter || username === userFilter;
                const statusMatch = !statusFilter || status === statusFilter;
                row.style.display = userMatch && statusMatch ? '' : 'none';
            });
        }


        document.querySelectorAll('.status-select').forEach(select => {
            select.addEventListener('change', function() {
                changedRecords.add(this.dataset.recordId);
                const row = this.closest('tr');
                row.setAttribute('data-status', this.value);
            });
        });

        function saveChanges() {
            const updates = Array.from(changedRecords).map(recordId => {
                const select = document.querySelector(`select[data-record-id="${recordId}"]`);
                const remarkInput = document.querySelector(`input.admin-remark[data-record-id="${recordId}"]`);
        
                return {
                    recordId: recordId,
                    status: select.value,
                    adminRemark: remarkInput.value
                };
            });

            if (updates.length === 0) {
                alert('No changes to save');
                return;
            }

            fetch('/update_status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ updates: updates })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success' || data.status === 'partial') {
                    if (data.failed && data.failed.length > 0) {
                        alert(`Some updates failed. Failed IDs: ${data.failed.join(', ')}`);
                    } else {
                        alert('Changes saved successfully');
                    }
                    changedRecords.clear();
                    
                    // Update the data-status attributes for filtered views
                    updates.forEach(update => {
                        const select = document.querySelector(`select[data-record-id="${update.recordId}"]`);
                        const row = select ? select.closest('tr') : null;
                        if (row) {
                            row.setAttribute('data-status', update.status);
                        }
                    });
                } else {
                    alert(data.message || 'Error saving changes');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert(`Error saving changes: ${error.message}`);
            });
        }

        // Add error handler for initial page load
        window.addEventListener('error', function(e) {
            console.error('Page Error:', e.error);
        });
    </script>
</body>
</html>
"""

@app.route("/admin", methods=["GET"])
def admin_page():
    global logged_in_user
    if logged_in_user != "admin":
        return redirect(url_for("login"))
    
    # Fetch all punch records from MongoDB
    records = list(punch_collection.find().sort("timestamp", DESCENDING))
    return render_template_string(ADMIN_TEMPLATE, records=records)

@app.route("/update_status", methods=["POST"])
def update_status():
    try:
        if logged_in_user != "admin":
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        updates = request.json.get('updates', [])
        if not updates:
            return jsonify({"status": "error", "message": "No updates provided"}), 400

        successful_updates = []
        failed_updates = []

        for update in updates:
            try:
                record_id = update.get('recordId')
                new_status = update.get('status')
                admin_remark = update.get('adminRemark', '')

                if not all([record_id, new_status]):
                    failed_updates.append(record_id)
                    continue

                object_id = ObjectId(record_id)
                result = punch_collection.update_one(
                    {"_id": object_id},
                    {
                        "$set": {
                            "status": new_status,
                            "adminRemark": admin_remark,
                            "statusChangedAt": get_time_with_offset()
                        }
                    }
                )

                if result.modified_count > 0:
                    successful_updates.append(record_id)
                else:
                    failed_updates.append(record_id)

            except Exception as e:
                logger.error(f"Error updating record {record_id}: {str(e)}")
                failed_updates.append(record_id)

        return jsonify({
            "status": "success" if not failed_updates else "partial",
            "successful": successful_updates,
            "failed": failed_updates
        })

    except Exception as e:
        logger.error(f"Update status error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/", methods=["GET", "POST"])
def login():
    global logged_in_user
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in users and users[username] == password:
            logged_in_user = username
            if username == "admin":
                return redirect(url_for("admin_page"))
            return redirect(url_for("main_page"))
        else:
            error = "Invalid username or password."
            return render_template_string(LOGIN_PAGE, error=error)
    
    logged_in_user = None
    return render_template_string(LOGIN_PAGE)

@app.route("/main", methods=["GET"])
def main_page():
    global logged_in_user
    if logged_in_user:
        # Get user's last punch status from MongoDB
        last_punch = get_user_last_punch(logged_in_user)
        initial_status = last_punch['action'] if last_punch else None
        return render_template_string(HTML_TEMPLATE, username=logged_in_user, initial_status=initial_status)
    return redirect(url_for("login"))

@app.route("/logout", methods=["GET", "POST"])
def logout():
    global logged_in_user
    logged_in_user = None  # Clear the login state
    return redirect(url_for("login"))


@app.route('/get_geofence_status', methods=['POST'])
def get_geofence_status():
    try:
        if not logged_in_user:
            logger.error("User not logged in")
            return jsonify({'status': 'error', 'message': 'Not logged in'}), 403
            
        user_location = request.json.get('latitude'), request.json.get('longitude')
        logger.info(f"User location: {user_location}")
        
        if None in user_location:
            logger.error("Invalid coordinates received")
            return jsonify({'status': 'error', 'message': 'Invalid coordinates'}), 400
        
        distance = calculate_distance(user_location)
        logger.info(f"Calculated distance: {distance}")
        
        status = 'Inside Geofence' if distance <= geofence_radius else 'Outside Geofence'
        return jsonify({'status': status, 'distance': distance})
    except Exception as e:
        logger.error(f"Geofence error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/last_punch_status', methods=['GET'])
def last_punch_status():
    global logged_in_user
    if not logged_in_user:
        return jsonify({'action': None})
    
    last_punch = get_user_last_punch(logged_in_user)
    if last_punch:
        return jsonify({
            'action': last_punch['action'],
            'timestamp': last_punch['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'action': None})

@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.route('/punch', methods=['POST'])
def punch_action():
    try:
        if not logged_in_user:
            logger.error("Punch attempt without login")
            return jsonify({"status": "error", "message": "User not logged in"}), 403

        data = request.json
        logger.info(f"Received punch data: {data}")

        action = data.get('action')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        userRemark = data.get('userRemark', '')

        if not all([action, latitude is not None, longitude is not None]):
            logger.error("Missing required punch data")
            return jsonify({"status": "error", "message": "Invalid data"}), 400

        user_location = (latitude, longitude)
        distance = calculate_distance(user_location)
        logger.info(f"Distance from geofence center: {distance}")

        if distance > geofence_radius:
            logger.warning(f"User outside geofence. Distance: {distance}")
            return jsonify({"status": "error", "message": "Outside Geofence"}), 403

        current_time = get_time_with_offset()
        punch_record = {
            "username": logged_in_user,
            "action": action,
            "latitude": latitude,
            "longitude": longitude,
            "distance_from_center": distance,
            "timestamp": current_time,
            "status": "pending",
            "userRemark": userRemark,
            "statusChangedAt": None,
            "adminRemark": "",
            "workDuration": None
        }

        if action == "Punch Out":
            try:
                last_punch_in = punch_collection.find_one(
                    {
                        "username": logged_in_user,
                        "action": "Punch In"
                    },
                    sort=[("timestamp", -1)]
                )
                if last_punch_in:
                    duration = calculate_work_duration(last_punch_in['timestamp'], current_time)
                    punch_record['workDuration'] = duration
                    logger.info(f"Calculated work duration: {duration}")
            except Exception as e:
                logger.error(f"Error calculating work duration: {str(e)}")

        try:
            result = punch_collection.insert_one(punch_record)
            logger.info(f"Punch record inserted. ID: {result.inserted_id}")
            return jsonify({
                "status": "success", 
                "message": f"{action} recorded for {logged_in_user}"
            }), 200
        except Exception as e:
            logger.error(f"MongoDB insert error: {str(e)}")
            return jsonify({"status": "error", "message": "Database error"}), 500

    except Exception as e:
        logger.error(f"Punch action error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.before_request
def check_mongo_connection():
    try:
        # Ping MongoDB
        client.admin.command('ping')
    except Exception as e:
        logger.error(f"MongoDB connection error: {str(e)}")
        return jsonify({"status": "error", "message": "Database connection error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
