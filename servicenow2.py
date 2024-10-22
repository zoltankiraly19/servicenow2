from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import ibm_boto3
from ibm_botocore.client import Config, ClientError

app = Flask(__name__)
CORS(app)

# IBM Cloud Object Storage configuration
cos = ibm_boto3.client(
    's3',
    ibm_api_key_id='UZ0-SGtOYDF0aGrbKO9fAvBwy901L0xZqd7dJfWveV-2',
    ibm_service_instance_id='crn:v1:bluemix:public:cloud-object-storage:global:a/c9b79e3ae1594628bb4d214193b9cb75:e310fa1f-ff9f-443e-b3fd-c86719b7e9e6:bucket:elekteszt',
    config=Config(signature_version='oauth'),
    endpoint_url='https://s3.us-south.cloud-object-storage.appdomain.cloud'
)

# Helper function to store session data in IBM COS
def store_session_data(file_name, data):
    try:
        print(f"Storing {file_name} in Cloud Object Storage with data: {data}")
        response = cos.put_object(Bucket='elekteszt', Key=file_name, Body=data)
        print(f"Store response: {response}")
    except ClientError as e:
        print(f"Error storing {file_name}: {e}")

# Helper function to retrieve session data from IBM COS
def get_session_data(file_name):
    try:
        print(f"Attempting to retrieve {file_name} from Cloud Object Storage...")
        response = cos.get_object(Bucket='elekteszt', Key=file_name)
        data = response['Body'].read().decode('utf-8')
        print(f"Retrieved {file_name} with data: {data}")
        return data
    except ClientError as e:
        print(f"Error retrieving {file_name}: {e}")
        return None

@app.route('/')
def login():
    return jsonify({"message": "Please provide username and password"})

@app.route('/get_token', methods=['POST'])
def get_token():
    request_data = request.json
    username = request_data.get('username')
    password = request_data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    auth_data = {
        'grant_type': 'password',
        'client_id': '45f3f2fb2ead4928ab994c64c664dfdc',
        'client_secret': 'fyHL1.@d&7',
        'username': username,
        'password': password
    }

    response = requests.post('https://dev227667.service-now.com/oauth_token.do', data=auth_data)

    if response.status_code == 200:
        access_token = response.json().get('access_token')
        store_session_data(f'{username}_token', access_token)
        store_session_data(f'{username}_id', username)
        return jsonify({"access_token": access_token}), 200
    else:
        return jsonify({"error": "Authentication failed", "details": response.text}), 400

@app.route('/get_servicenow_data', methods=['POST'])
def get_servicenow_data():
    request_data = request.json
    username = request_data.get('username')

    access_token = get_session_data(f'{username}_token')
    if access_token is None:
        return jsonify({"error": "Token not available"}), 400

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Fetch assignment groups
    response_groups = requests.get('https://dev227667.service-now.com/api/now/table/sys_user_group', headers=headers)
    if response_groups.status_code == 200:
        groups = response_groups.json().get('result', [])
        assignment_groups = [{"name": group["name"], "sys_id": group["sys_id"]} for group in groups]
        store_session_data(f'{username}_assignment_groups', str(assignment_groups))
    else:
        return jsonify({"error": "Failed to retrieve assignment groups"}), 400

    # Fetch priorities
    response_priorities = requests.get(
        'https://dev227667.service-now.com/api/now/table/sys_choice?sysparm_query=name=incident^element=priority',
        headers=headers)
    if response_priorities.status_code == 200:
        priorities = [{"label": priority["label"], "value": priority["value"]} for priority in response_priorities.json().get('result', [])]
        store_session_data(f'{username}_priorities', str(priorities))
    else:
        return jsonify({"error": "Failed to retrieve priorities"}), 400

    return jsonify({"message": "Data retrieved successfully"}), 200

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    request_data = request.json
    username = request_data.get('username')

    access_token = get_session_data(f'{username}_token')
    current_caller_id = get_session_data(f'{username}_caller_id')

    if access_token is None:
        return jsonify({"error": "Token not available"}), 400

    if current_caller_id is None:
        return jsonify({"error": "Caller ID not available"}), 400

    short_description = request_data.get('short_description')
    assignment_group_sys_id = request_data.get('assignment_group_sys_id')
    priority = request_data.get('priority')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    ticket_data = {
        "short_description": short_description,
        "assignment_group": assignment_group_sys_id,
        "priority": priority,
        "caller_id": current_caller_id
    }

    response = requests.post('https://dev227667.service-now.com/api/now/table/incident', json=ticket_data, headers=headers)

    if response.status_code == 201:
        return jsonify({"message": "Ticket created successfully", "ticket_number": response.json().get('result', {}).get('number')}), 201
    else:
        return jsonify({"error": "Failed to create ticket", "details": response.text}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
