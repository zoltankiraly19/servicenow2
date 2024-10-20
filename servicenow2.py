from flask import Flask, request, jsonify, session
import requests
from flask_cors import CORS
from flask_session import Session

app = Flask(__name__)
CORS(app)

# Flask-Session konfiguráció
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 's3cr3t_k3y'  # Ezt a titkos kulcsot egyéni és biztonságos jelszóra kell cserélni
app.config['SESSION_PERMANENT'] = False
Session(app)

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.json
    auth_data = {
        'grant_type': 'password',
        'client_id': '45f3f2fb2ead4928ab994c64c664dfdc',
        'client_secret': 'fyHL1.@d&7',
        'username': data.get('username'),
        'password': data.get('password')
    }

    response = requests.post('https://dev227667.service-now.com/oauth_token.do', data=auth_data)

    if response.status_code == 200:
        access_token = response.json().get('access_token')
        session['access_token'] = access_token  # A token sessionben tárolódik
        session['current_user_id'] = data.get('username')  # A felhasználónév sessionben tárolódik
        return jsonify({"access_token": access_token}), 200
    else:
        return jsonify({"error": "Authentication failed", "details": response.text}), 400

@app.route('/get_servicenow_data', methods=['POST'])
def get_servicenow_data():
    if 'access_token' not in session:
        return jsonify({"error": "Token not available. Please authenticate first."}), 400

    if 'current_user_id' not in session:
        return jsonify({"error": "User ID not available. Please authenticate first."}), 400

    access_token = session['access_token']
    current_user_id = session['current_user_id']

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Lekérjük a felhasználó sys_id-ját a user_name alapján
    response_user = requests.get(
        f"https://dev227667.service-now.com/api/now/table/sys_user?sysparm_query=user_name={current_user_id}",
        headers=headers)

    if response_user.status_code == 200:
        users = response_user.json().get('result', [])
        if users:
            session['current_caller_id'] = users[0].get("sys_id")

    # Assignment groupok lekérdezése és tárolása a sessionben
    response_groups = requests.get('https://dev227667.service-now.com/api/now/table/sys_user_group', headers=headers)
    if response_groups.status_code == 200:
        groups = response_groups.json().get('result', [])
        session['assignment_groups'] = [{"name": group["name"], "sys_id": group["sys_id"]} for group in groups]

    # Priority lekérdezés és tárolása a sessionben
    response_priorities = requests.get(
        'https://dev227667.service-now.com/api/now/table/sys_choice?sysparm_query=name=incident^element=priority',
        headers=headers)
    if response_priorities.status_code == 200:
        priorities = response_priorities.json().get('result', [])
        session['priorities'] = [{"label": priority["label"], "value": priority["value"]} for priority in priorities]

    # Nem küldünk vissza adatokat, csak jelzést, hogy a lekérés sikeres volt
    return jsonify({"message": "ServiceNow data retrieved and stored successfully."}), 200

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    if 'access_token' not in session:
        return jsonify({"error": "Token not available. Please authenticate first."}), 400

    if 'current_caller_id' not in session:
        return jsonify({"error": "Caller ID not available. Please retrieve ServiceNow data first."}), 400

    access_token = session['access_token']
    current_caller_id = session['current_caller_id']

    data = request.json

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    ticket_data = {
        "short_description": data.get('short_description'),
        "assignment_group": data.get('assignment_group_sys_id'),
        "priority": data.get('priority'),
        "caller_id": current_caller_id
    }

    response = requests.post('https://dev227667.service-now.com/api/now/table/incident', json=ticket_data,
                             headers=headers)

    if response.status_code == 201:
        return jsonify({"message": "Ticket created successfully",
                        "ticket_number": response.json().get('result', {}).get('number')}), 201
    else:
        return jsonify({"error": "Failed to create ticket", "details": response.text}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
