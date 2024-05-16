import json
import getpass
import subprocess
from awscrt import mqtt, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
import json
from utils.command_line_utils import CommandLineUtils
import os
host = "127.0.0.1"
pi_id = 0
key_path = r"C:\Users\Lenna\Documents\Bastion_key.pem"
cmdData = CommandLineUtils.parse_sample_input_pubsub()
received_count = 0
received_all_event = threading.Event()
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    #print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        resubscribe_future.add_done_callback(on_resubscribe_complete)
# Callback when a connection has been disconnected or shutdown successfully
def on_connection_closed(connection, callback_data):
    print("Connection closed")


def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))
def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    #print("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))
    
def on_connection_interrupted(connection, error, **kwargs):
    return


def request_tunnel(command, pi_id, user, password): 
    message_data = {
        'command': command,
        'pi_id': pi_id
    }
    payload = json.dumps(message_data)
    pi_topic = "pi/"+ pi_id
    print("Sending tunnel request to topic '{}'...".format(pi_topic))
    mqtt_connection.publish(
        topic=pi_topic,
        payload=payload,
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    message_data = {
        'command': command,
        'pi_id': pi_id,
        'user' : user,
        'password': password 
    }
    payload = json.dumps(message_data)
    print("Sending tunnel request to bastion")
    mqtt_connection.publish(
        topic="message_topic/bastion",
        payload=payload,
        qos=mqtt.QoS.AT_LEAST_ONCE
        )
    
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    message_data = json.loads(payload.decode('utf-8'))
    received_pi_id = message_data.get('pi_id')
    received_ssh_port = message_data.get('port')

    # Check if the received pi_id matches the expected pi_id
    if received_pi_id == pi_id:
        # Store the received SSH port for later connection
        ssh_port = received_ssh_port
        run_ssh_command(host , ssh_port)

def run_ssh_command(host, port):
    try:
        command = f'start cmd /c ssh pi@{host} -o ProxyCommand="ssh -W %h:%p ubuntu@ec2-34-241-140-26.eu-west-1.compute.amazonaws.com" -p {port} -v'
        result = subprocess.run(command, shell=True)
        if result == 0:
            print("SSH command executed successfully.")
            return True
        else:
            return False
    except Exception as e:
        print("An error occurred while executing the SSH command:", e)
    

    
        
# Callback when a connection attempt fails
def on_connection_failure(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionFailureData)
    print("Connection failed with error code: {}".format(callback_data.error))

# Callback when a connection has been disconnected or shutdown successfully
def on_connection_closed(connection, callback_data):
    print("Connection closed")
if __name__ == '__main__':
    proxy_options = None
    if cmdData.input_proxy_host is not None and cmdData.input_proxy_port != 0:
        proxy_options = http.HttpProxyOptions(
            host_name=cmdData.input_proxy_host,
            port=cmdData.input_proxy_port)

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=cmdData.input_endpoint,
        port=cmdData.input_port,
        cert_filepath=cmdData.input_cert,
        pri_key_filepath=cmdData.input_key,
        ca_filepath=cmdData.input_ca,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=cmdData.input_clientId,
        clean_session=False,
        keep_alive_secs=30,
        http_proxy_options=proxy_options,
        on_connection_success=on_connection_success,
        on_connection_failure=on_connection_failure,
        on_connection_closed=on_connection_closed)
    if not cmdData.input_is_ci:
        print(f"Connecting to {cmdData.input_endpoint} with client ID '{cmdData.input_clientId}'...")
    else:
        print("Connecting to endpoint with client ID")
    connect_future = mqtt_connection.connect()

    connect_future.result()
    print("Connected!") 
    tunnel_topic = cmdData.input_topic
    print("Subscribing to topic '{}'...".format(tunnel_topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic= tunnel_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)
    
    ssh_host = 'pi@127.0.0.1'
    while True:
        command = input("Enter the command: ")
        pi_id = input("Enter the pi_id: ")
        user = input("Enter username: ")
        password = input("Enter password : ")
        
        if request_tunnel(command, pi_id, user,password):
            break
        
