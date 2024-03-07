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
import queue
import select
import subprocess
import re  # Import the 're' module for regular expression matching
client_topic = "client/tunnel"
cmdData = CommandLineUtils.parse_sample_input_pubsub()
received_count = 0
received_all_event = threading.Event()
bastion_address = "ubuntu@ec2-34-241-140-26.eu-west-1.compute.amazonaws.com"

port_condition = threading.Condition()
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

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

def get_pi_id():
    pi_id_file = "/home/pi/pi_id.txt"  # Replace with the actual path to your pi_id.txt file
    if os.path.exists(pi_id_file):
        with open(pi_id_file, "r") as file:
            pi_id = file.read().strip()
            return pi_id
    else:
        print("Pi ID file not found.")
        return None

def check_tunnel_status():
    tunnel_host = "localhost"
    tunnel_port = 22

    try:
        result = subprocess.run(["nc", "-z", "-v", "-w", "5", tunnel_host, str(tunnel_port)], capture_output=True, text=True)
        if result.returncode == 0:
            pi_id = get_pi_id() 

            print("Tunnel is ready to be used.")
            message_data = {
                 'port': bastion_port,
                 'pi_id': pi_id
                }
            payload = json.dumps(message_data)

            print("sending port to client '{}'...".format(client_topic))
            mqtt_connection.publish(
                topic=client_topic,
                payload=payload,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
        else:
            print("Tunnel is not ready.")
    except Exception as e:
        print("Error checking tunnel status:", str(e))
        
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    threading.Thread(target= handle_message, args=((topic, payload, dup, qos, retain))).start()
def handle_message(topic, payload, dup, qos, retain):
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
                with port_condition:
                    time.sleep(0.1) 
                    print("port condition waitin")
                    port_condition.wait()  # Wait for the condition to be notified
                    print(bastion_port)
                if bastion_port is None:
                    print("Did not receive port from bastion host.")
                    return
                print("Executing tunnel command")
                ssh_command = "ssh -N -R " f'{bastion_port}' ":localhost:22 -i Bastion_key.pem " f'{bastion_address}' " -o StrictHostKeyChecking=no ExitOnForwardFailure=yes"
                print(ssh_command)
                try:
                   
                    # Execute SSH command
                    ssh_process = subprocess.Popen(
                        ssh_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,  # Use universal_newlines for text mode
                        shell=True
                    )
                    
                    check_tunnel_status()
                except Exception as e:
                    print("Error executing SSH command:", str(e))        
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
 
def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    print("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))
    
def on_bastion_port_received(topic, payload, dup, qos, retain, **kwargs):
    threading.Thread(target=handle_bastion_port, args=(topic, payload, dup, qos, retain)).start()
def handle_bastion_port(topic, payload, dup, qos, retain):
    print("Received port from bastion host: {}".format(payload))
    global bastion_port
    try:
        message_data = json.loads(payload.decode())  # Decode payload to string before parsing as JSON
        with port_condition:
            bastion_port = message_data.get('port')
            port_condition.notify()
            print("port condition")  # Notify the waiting thread
    except json.JSONDecodeError as e:
        print("Error decoding JSON payload: {}".format(e))


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

    message_topic = cmdData.input_topic
    bastion_topic = "bastion/port"

    print("Subscribing to topic '{}'...".format(message_topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=message_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)

    subscribe_result = subscribe_future.result()
    print("Subscribed with {}".format(str(subscribe_result['qos'])))
    #Subscribe to the topic where the bastion host will provide the port

    print("Subscribing to topic '{}'...".format(bastion_topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=bastion_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_bastion_port_received)

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
