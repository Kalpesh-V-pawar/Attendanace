import sys
sys.path.append(r'C:\users\kalpe\appData\roaming\python\python312\site-packages')

from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from haversine import haversine, Unit
from pymongo import MongoClient
import datetime

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
}

logged_in_user = None

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
    let hasPunchedIn = false;
    let isProcessing = false; // Flag to prevent multiple clicks

    // Fetch user's location using Geolocation API
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLat = position.coords.latitude;
                const userLng = position.coords.longitude;

                // Send location to the server to check geofence status
                fetch('/get_geofence_status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ latitude: userLat, longitude: userLng })
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('geofence-indicator').innerText = data.status;

                    if (data.status === 'Outside Geofence') {
                        const coordinates = `Lat: ${userLat}, Lng: ${userLng}`;
                        document.getElementById('coordinates').innerText = coordinates;
                        document.getElementById('user-coordinates').style.display = 'block';
                        document.getElementById('punch-in').style.display = 'none';
                        document.getElementById('punch-out').style.display = 'none';
                    } else {
                        updateButtonVisibilityBasedOnLastPunch(); // Update button visibility based on last punch
                    }
                });
            },
            (error) => {
                console.error("Geolocation Error:", error.message);
                document.getElementById('geofence-indicator').innerText = "Location Error";
            }
        );
    } else {
        console.error("Geolocation not supported by this browser.");
        document.getElementById('geofence-indicator').innerText = "Geolocation not supported.";
    }

    // Fetch the last punch status from the server
    function updateButtonVisibilityBasedOnLastPunch() {
        fetch('/last_punch_status')
            .then(response => response.json())
            .then(data => {
                if (data.action === 'Punch In') {
                    hasPunchedIn = true;
                } else if (data.action === 'Punch Out') {
                    hasPunchedIn = false;
                }
                updateButtonVisibility();
            });
    }

    // Punch actions
    document.getElementById('punch-in').addEventListener('click', () => {
        if (!isProcessing) {
            handlePunchAction('Punch In');
        }
    });

    document.getElementById('punch-out').addEventListener('click', () => {
        if (!isProcessing) {
            handlePunchAction('Punch Out');
        }
    });

    // Handle punch action with feedback and prevention of multiple clicks
    function handlePunchAction(action) {
        isProcessing = true; // Prevent further clicks
        showStatusMessage("Your input is getting saved...");
        disableButtons();

        navigator.geolocation.getCurrentPosition((position) => {
            const userLat = position.coords.latitude;
            const userLng = position.coords.longitude;
            fetch('/punch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: action,
                    latitude: userLat,
                    longitude: userLng
                })
            })
            .then(response => response.json())
            .then(data => {
                addPunchRecord(data.message);
                hasPunchedIn = (action === 'Punch In'); // Update status locally
                updateButtonVisibility();
                showStatusMessage("Your input is saved!");
                setTimeout(() => {
                    isProcessing = false; // Re-enable clicks after delay
                    enableButtons();
                }, 5000); // 5-second delay
            });
        });
    }

    function updateButtonVisibility() {
        if (hasPunchedIn) {
            document.getElementById('punch-in').style.display = 'none';
            document.getElementById('punch-out').style.display = 'block';
        } else {
            document.getElementById('punch-in').style.display = 'block';
            document.getElementById('punch-out').style.display = 'none';
        }
    }

    // Utility to add punch record to the history
    function addPunchRecord(record) {
        const listItem = document.createElement('li');
        listItem.textContent = record;
        document.getElementById('history-list').appendChild(listItem);
    }

    // Show status messages to the user
    function showStatusMessage(message) {
        const statusElement = document.createElement('p');
        statusElement.id = 'status-message';
        statusElement.textContent = message;
        document.body.appendChild(statusElement);

        // Remove message after some time
        setTimeout(() => {
            const existingStatusElement = document.getElementById('status-message');
            if (existingStatusElement) {
                existingStatusElement.remove();
            }
        }, 5000);
    }

    // Disable punch buttons
    function disableButtons() {
        document.getElementById('punch-in').disabled = true;
        document.getElementById('punch-out').disabled = true;
    }

    // Enable punch buttons
    function enableButtons() {
        document.getElementById('punch-in').disabled = false;
        document.getElementById('punch-out').disabled = false;
    }
</script>


</body>
</html>
"""
@app.route("/", methods=["GET", "POST"])
def login():
    global logged_in_user
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in users and users[username] == password:
            logged_in_user = username  # Set logged-in user
            return redirect(url_for("main_page"))
        else:
            error = "Invalid username or password."
            return render_template_string(LOGIN_PAGE, error=error)
    
    # Reset login state on reload
    logged_in_user = None
    return render_template_string(LOGIN_PAGE)

@app.route("/main", methods=["GET"])
def main_page():
    global logged_in_user
    if logged_in_user:  # Check if a user is logged in
        return render_template_string(HTML_TEMPLATE, username=logged_in_user)
    else:
        return redirect(url_for("login"))

@app.route("/logout", methods=["GET", "POST"])
def logout():
    global logged_in_user
    logged_in_user = None  # Clear the login state
    return redirect(url_for("login"))


@app.route('/get_geofence_status', methods=['POST'])
def get_geofence_status():
    user_location = request.json.get('latitude'), request.json.get('longitude')
    distance = calculate_distance(user_location)
    status = 'Inside Geofence' if distance <= geofence_radius else 'Outside Geofence'
    return jsonify({'status': status, 'distance': distance})

@app.route('/last_punch_status', methods=['GET'])
def last_punch_status():
    last_punch = punch_collection.find_one(sort=[("timestamp", -1)])  # Get the last punch record
    if last_punch:
        return jsonify({
            'action': last_punch['action'],
            'timestamp': last_punch['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'action': None})  # No punch record found


@app.route('/punch', methods=['POST'])
def punch():
    action = request.json.get('action')
    latitude = request.json.get('latitude')
    longitude = request.json.get('longitude')
    timestamp = datetime.datetime.now()

    # Store the record in MongoDB
    punch_record = {
        'action': action,
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': timestamp
    }
    punch_collection.insert_one(punch_record)

    return jsonify({'message': f"{action} at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"})

if __name__ == '__main__':
    app.run(debug=True)
