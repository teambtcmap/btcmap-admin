from flask import Flask, render_template, request, redirect, url_for, flash
import requests
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a random secret key

@app.route('/')
def home():
    return render_template('index.html')  # Render the index.html template

@app.route('/show_area', methods=['POST'])
def show_area():
    api_key = request.form['api_key']
    area_id = request.form['area_id']

    # Create the JSON-RPC payload
    json_rpc_payload = {
        "jsonrpc": "2.0",
        "method": "getarea",
        "params": {
            "token": api_key,
            "id": area_id
        },
        "id": 1
    }

    # Send the request to the BTC Map API
    url = "https://api.btcmap.org/rpc"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(json_rpc_payload))

    # Check the response
    if response.status_code == 200:
        response_data = response.json()
        if 'result' in response_data:
            area_data = response_data['result']
            return render_template('show_area.html', area_data=area_data)
        else:
            flash(f"Error retrieving area: {response_data.get('error', 'Unknown error')}", "error")
    else:
        flash(f"HTTP Error: {response.status_code} - {response.text}", "error")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
