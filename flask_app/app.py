from flask import Flask, render_template, request, redirect, url_for, flash
import requests
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session

# Home page
@app.route('/')
def home():
    return render_template('index.html')

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
    api_key = request.form['api_key']
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


if __name__ == '__main__':
    app.run(debug=True)
