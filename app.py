from flask import Flask, request
import json
from datetime import datetime
import requests
import boto3
from uhashring import HashRing
from ec2_node.ec2Node import Ec2Node

ec2_node = Ec2Node(8080)


def get_live_node_list() -> []:
    live_nodes = []
    try:
        app.logger.info('get_live_node_list')
        now = get_current_time()
        response = table.scan()
        app.logger.info(f'Table scan response: {response}')
        live_nodes = [item['IP'] for item in response['Items'] if
                      float(item['lastActiveTime']) >= now - 60000]

    except Exception as e:
        app.logger.info(f'Error in get_live_node_list: {e}')

    return live_nodes


dynamodb = boto3.resource('dynamodb', region_name="us-east-2")
table = dynamodb.Table('ActiveNodes')
app = Flask(__name__)
nodes_hash_ring = HashRing(nodes=get_live_node_list())


# TODO:
# Routes:
# 1. Health Check
# 2. put (str_key, data, expiration_date)
# 3. get(str_key) → null or data

# Functions:
# 1. Storing data in this nodes cache

def get_current_time():
    return int(round(datetime.now().timestamp()))


@app.route('/get', methods=['GET'])
def get():
    """
    Main API entry point
    get(str_key) → null or data
    :return: null or data
    """
    live_nodes = get_live_node_list()
    num_live_nodes = len(live_nodes)
    print(f'Here in /get')
    if num_live_nodes < 2:
        app.logger.info(f'{num_live_nodes} nodes still alive')
        # TODO: handle no live nodes

    key = request.args.get('str_key')
    node, alt_node = get_target_and_alt_node_ips(key)
    try:
        ans = ec2_node.get_data_and_get_req(key, node)
    except requests.exceptions.ConnectionError:
        try:
            ans = ec2_node.get_data_and_get_req(key, alt_node)
        except requests.exceptions.ConnectionError:
            ans = json.dumps({'status_code': 404})
    update_health_table()
    return ans.json().get('item')


@app.route('/put', methods=['GET', 'POST'])
def put():
    """
    Main API entry point
    put (str_key, data, expiration_date)
    """
    live_nodes = get_live_node_list()
    num_live_nodes = len(live_nodes)
    if num_live_nodes < 2:
        app.logger.info(f'{num_live_nodes} nodes still alive')
        # TODO: handle no live nodes

    key = request.args.get('str_key')
    data = request.args.get('data')
    expiration_date = request.args.get('expiration_date')
    node, alt_node = get_target_and_alt_node_ips(key)
    try:
        ans = ec2_node.store_data_and_post_req(key, data, expiration_date, node)
    except requests.exceptions.ConnectionError:
        try:
            ans = ec2_node.store_data_and_post_req(key, data, expiration_date, alt_node)
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
        res = json.dumps(
            {'status code': 400, 'item': f"Error: {e}"})
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


def get_target_node(key, nodes):
    hr = HashRing(nodes=nodes)
    return hr.get_node(key)


def update_live_nodes():
    live_nodes_list = get_live_node_list()
    for node_key in nodes_hash_ring.nodes():
        if node_key not in live_nodes_list:
            nodes_hash_ring.remove_node(node_key)


def get_target_and_alt_node_ips(key):
    update_live_nodes()
    main_node = nodes_hash_ring.get_node(key)
    nodes_hash_ring.remove_node(main_node)
    alt_node = nodes_hash_ring.get_node(key)
    nodes_hash_ring.add_node(main_node)
    return main_node, alt_node


@app.route('/health-check', methods=['GET', 'POST'])
def health_check():
    app.logger.info(f'{ip_address} node still alive')
    return "200"


@app.route('/')
def hello_world():
    print(f'Here in hello world')
    return 'Hello World!'


if __name__ == '__main__':
    ip_address = requests.get('https://api.ipify.org').text
    ec2_node.ip = ip_address
    app.logger.info(f'My public IP address is: {ip_address}')
    app.run(host='0.0.0.0', port=8080)
