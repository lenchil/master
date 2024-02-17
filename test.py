from awscrt import mqtt, http
from awsiot import mqtt_connection_builder
import sys
import threading
import json
from utils.command_line_utils import CommandLineUtils
import os
import subprocess
import getpass
import os
import time
cmdData = CommandLineUtils.parse_sample_input_pubsub()
received_count = 0
received_all_event = threading.Event()

def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        resubscribe_future.add_done_callback(on_resubscribe_complete)

def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))

def get_pi_id():
    pi_id_file = "/home/lennard/master/pi_id.txt"  # Replace with the actual path to your pi_id.txt file
    if os.path.exists(pi_id_file):
        with open(pi_id_file, "r") as file:
            pi_id = file.read().strip()
            return pi_id
    else:
        print("Pi ID file not found.")
        return None

# Create an event to wait for the port
port_event = threading.Event()

def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    
    try:
        message_data = json.loads(payload)
        command = message_data.get('command')
        pi_id = message_data.get('pi_id')  # Unique identifier for each Pi
        
        stored_pi_id = get_pi_id()
        if stored_pi_id is None:
            print("Pi ID not found.")
            return
            
        if pi_id == stored_pi_id:
            if command == 'Tunnel':
                print("Initiating reverse SSH tunnel request for Pi {}...".format(pi_id))
                # Add the SSH tunnel command for the specific Pi here
                subprocess.run(["ssh", "-R", f'{port}:localhost:22', '-i', 'ssh_test.pem' "pi@127.0.0.1"])
                
                # Wait for the port to be provided by the bastion host
                print("Waiting for port from bastion host...")
                port_event.wait()
                print("Received port from bastion host!")
                
                # Continue with the rest of the logic
                # ...
                
            else:
                print("Invalid command.")
        else:
            print("Pi ID does not match the stored Pi ID.")
            
    except json.JSONDecodeError as e:
        print("Error decoding JSON payload: {}".format(e))
    
    global received_count
    received_count += 1
    if received_count == cmdData.input_count:
        received_all_event.set()

# Function to set the port provided by the bastion host
def set_bastion_port(port):
    # Set the port and notify the waiting thread
    cmdData.input_port = port
    port_event.set()

def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    print("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))
    
    # Subscribe to the topic where the bastion host will provide the port
    bastion_topic = "bastion/port"
    print("Subscribing to topic '{}'...".format(bastion_topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=bastion_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_bastion_port_received)

    subscribe_result = subscribe_future.result()
    print("Subscribed with {}".format(str(subscribe_result['qos'])))

def on_bastion_port_received(topic, payload, dup, qos, retain, **kwargs):
    print("Received port from bastion host: {}".format(payload))
    set_bastion_port(payload)

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

    message_topic = cmdData.input_topic

    print("Subscribing to topic '{}'...".format(message_topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=message_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)

    subscribe_result = subscribe_future.result()
    print("Subscribed with {}".format(str(subscribe_result['qos'])))

    # Wait for all messages to be received.
    if not received_all_event.is_set():
        print("Waiting for messages...")

    received_all_event.wait()
    print("{} message(s) received.".format(received_count))

    # Disconnect
    print("Disconnecting...")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    print("Disconnected!")

