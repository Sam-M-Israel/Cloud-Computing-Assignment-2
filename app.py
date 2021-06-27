from flask import Flask, request
import json
from datetime import datetime
import requests
import boto3
from ec2_node.ec2Node import Ec2Node
from ec2_node.nodeHashRing import NodeHashRing

ec2_node = Ec2Node(8080)

dynamodb = boto3.resource('dynamodb', region_name="us-east-2")
table = dynamodb.Table('ActiveNodes')
app = Flask(__name__)
nodes_hash_ring = NodeHashRing(table)

# TODO:
# Routes:
# 1. Health Check
# 2. put (str_key, data, expiration_date)
# 3. get(str_key) → null or data

# Functions:
# 1. Storing data in this nodes cache


def get_current_time():
    return int(round(datetime.now().timestamp())*1000)


@app.route('/get', methods=['GET'])
def get():
    """
    Main API entry point
    get(str_key) → null or data
    :return: null or data
    """
    nodes_hash_ring.update_live_nodes()
    key = request.args.get('str_key')
    node, alt_node = nodes_hash_ring.get_target_and_alt_node_ips(key)
    try:
        ans = ec2_node.get_data_and_get_req(key, node)
        ec2_node.secondary_node = node
    except requests.exceptions.ConnectionError:
        try:
            ans = ec2_node.get_data_and_get_req(key, alt_node)
            ec2_node.secondary_node = alt_node
        except requests.exceptions.ConnectionError:
            ans = json.dumps({'status_code': 404})
    update_health_table()

    if ans is None:
        return json.dumps({'status_code': 200,
                          'Invalid Key': f'Key, value pair for {key} doesn\"t exist in '
                                        'any cache in system'})
    return ans


@app.route('/put', methods=['GET', 'POST'])
def put():
    """
    Main API entry point
    put (str_key, data, expiration_date)
    """
    nodes_hash_ring.update_live_nodes()
    key = request.args.get('str_key')
    data = request.args.get('data')
    expiration_date = request.args.get('expiration_date')
    node, alt_node = nodes_hash_ring.get_target_and_alt_node_ips(key)
    try:
        ans = ec2_node.store_data_and_post_req(key, data, expiration_date, node)
        ec2_node.secondary_node = node
    except requests.exceptions.ConnectionError:
        try:
            ans = ec2_node.store_data_and_post_req(key, data, expiration_date, alt_node)
            ec2_node.secondary_node = alt_node
        except requests.exceptions.ConnectionError:
            ans = json.dumps({'status_code': 404})
    update_health_table()
    return ans.json()


# API calls between all of the nodes in the distributed cache system. Ideally not accessible by the user


@app.route('/api/get_val', methods=['GET'])
def get_value():
    """
    Get the value of the given key from THIS nodes cache
    :return: the data value of the given key from the cache
    """
    try:
        key = request.args.get('str_key')
        item = ec2_node.get_data_in_cache(key)
        res = json.dumps({'status code': 200, 'item': item})
        update_health_table()
    except Exception as e:
        res = json.dumps(
            {'status code': 400, 'item': f"Error: {e}"})
    return res


@app.route('/api/set_value', methods=['POST'])
def set_value():
    """
    Sets a key in THIS nodes cache with the data value
    :return: Status code
    """
    try:
        key = request.args.get('str_key')
        data = request.args.get('data')
        expiration_date = request.args.get('expiration_date')
        store_res = ec2_node.store_data(key, data, expiration_date)
        res = json.dumps({'status code': 200, 'item': store_res})
        update_health_table()
    except Exception as e:
        res = json.dumps({'status code': 400, 'item': f"Error: {e}"})
    return res


@app.route('/api/print-cache', methods=['GET','POST'])
def show_cache():
    """
    For Testing Purposes
    :return:
    """
    try:
        data = json.dumps(
            {'status code': 200, 'item': ec2_node.get_cache()})
    except Exception as e:
        data = json.dumps(
            {'status code': 400, 'item': f"Error: {e}"})
    return data


@app.route('/api/show_me_the_living', methods=['GET','POST'])
def get_live_nodes():
    live_nodes_list, _ = nodes_hash_ring.get_live_node_list()
    return json.dumps(
            {'status code': 200, 'item': live_nodes_list})


@app.route('/api/backup', methods=['GET','POST'])
def backup_node():
    try:
        data_to_backup = request.get_json(silent=True)
        print(data_to_backup)
        start_node = request.args.get('start_node')
        backup_res = ec2_node.backup_neighbors_cache(data_to_backup)
        if start_node == ec2_node.ip:
            print("Backups done")
        else:
            if not ec2_node.has_been_backed_up:
                nodes_hash_ring.update_live_nodes()
                node, alt_node = nodes_hash_ring.get_target_and_alt_node_ips("fake_Key")
                ec2_node.secondary_node = node if node not in nodes_hash_ring.live_nodes else alt_node
                ec2_node.backup_main_cache(ec2_node.ip)
                backup_res = ec2_node.backup_main_cache(start_node)
            res = json.dumps({'status code': 200, 'item': backup_res})
            update_health_table()
            ec2_node.has_been_backed_up = True
    except Exception as e:
        res = json.dumps({'status code': 400, 'item': f"Error: {e}"})
    return res


def update_health_table():
    timestamp = get_current_time()
    res = table.update_item(
        Key={
            'IP': ip_address
        },
        UpdateExpression='set lastActiveTime= :val1',
        ExpressionAttributeValues={
            ':val1': timestamp,
        }
    )
    app.logger.info(f'{res}')
    return timestamp


@app.route('/health-check', methods=['GET', 'POST'])
def health_check():
    time_stamp = update_health_table()
    print(f'{ip_address} node still alive at {time_stamp}')
    nodes_hash_ring.update_live_nodes()
    if nodes_hash_ring.do_backup is True and not ec2_node.has_been_backed_up:
        node, alt_node = nodes_hash_ring.get_target_and_alt_node_ips("fake_Key")
        ec2_node.secondary_node = node if node not in nodes_hash_ring.live_nodes else alt_node
        ec2_node.backup_main_cache(ec2_node.ip)
        ec2_node.has_been_backed_up = True
    return "200"


@app.route('/')
def hello_world():
    print(f'Here in hello world')
    timestamp = get_current_time()
    item = {'IP': ip_address,
            'lastActiveTime': timestamp
            }
    table.put_item(Item=item)
    nodes_hash_ring.update_live_nodes()
    return 'Hello World!'


if __name__ == '__main__':
    ip_address = requests.get('https://api.ipify.org').text
    ec2_node.ip = ip_address
    update_health_table()
    app.logger.info(f'My public IP address is: {ip_address}')
    app.run(host='0.0.0.0', port=8080)
