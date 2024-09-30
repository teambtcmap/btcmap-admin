from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session

# Home page
@app.route('/')
def home():
    return render_template('index.html')

#Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        api_key = request.form['api_key']

        # You can add validation for the API key here if needed.

        session['api_key'] = api_key  # Store the API key in the session
        flash('Logged in successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('index.html')

#Logout
@app.route('/logout')
def logout():
    session.pop('api_key', None)  # Remove API key from session
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

# Protect other routes if API key is not in the session
@app.before_request
def require_api_key():
    if request.endpoint not in ['login', 'home', 'logout'] and 'api_key' not in session:
        return redirect(url_for('home'))

# Get Areas
@app.route('/select_area', methods=['GET', 'POST'])
def select_area():
    # Fetch areas from the API
    try:
        response = requests.get('https://api.btcmap.org/v2/areas')
        response.raise_for_status()
        areas = response.json()  # Parse the JSON data

    except requests.exceptions.HTTPError as err:
        flash(f'HTTP error occurred: {err}', 'danger')
        areas = []

    except Exception as err:
        flash(f'Error: {err}', 'danger')
        areas = []

    return render_template('select_area.html', areas=areas)

# Show Area
@app.route('/show_area', methods=['POST'])
def show_area():
       
    # Retrieve the API key from the session
    api_key = session.get('api_key')
    area_id = request.form['area_id']

    # JSON-RPC payload for requesting area details
    json_rpc_payload = {
        "jsonrpc": "2.0",
        "method": "getarea",
        "params": {
            "token": api_key,
            "id": area_id
        },
        "id": 1
    }

    # Send request to BTC Map API
    url = "https://api.btcmap.org/rpc"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(json_rpc_payload))

    # Check if response was successful
    if response.status_code == 200:
        response_data = response.json()

        # Check if 'result' exists in the response
        if 'result' in response_data:
            area_data = response_data['result']
            return render_template('show_area.html', area_data=area_data)
        else:
            error_message = response_data.get('error', 'Unknown error')
            flash(f"Error retrieving area: {error_message}", "error")
    else:
        flash(f"HTTP Error: {response.status_code} - {response.text}", "error")

    # Redirect back to the index/home page on failure
    return redirect(url_for('home'))

#Update Area
@app.route('/update_area', methods=['POST'])
def update_area():
    api_key = request.form['api_key']
    area_id = request.form['area_id']
    tags = request.form.getlist('tags')

    for key, value in tags.items():
        # Create the JSON-RPC payload for each tag update
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "setareatag",
            "params": {
                "token": api_key,
                "id": area_id,
                "name": key,
                "value": value
            },
            "id": 1
        }

        # Send the request to the BTC Map API
        url = "https://api.btcmap.org/rpc"
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=json.dumps(json_rpc_payload))

        # Check for errors
        if response.status_code != 200 or 'error' in response.json():
            flash(f"Error updating tag {key}: {response.json().get('error', 'Unknown error')}", "danger")
            return redirect(url_for('show_area'))

    flash("Area tags updated successfully!", "success")
    return redirect(url_for('show_area'))


if __name__ == '__main__':
    app.run(debug=True)
