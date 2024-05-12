from awscrt import mqtt, http
from awsiot import mqtt_connection_builder
import json
from utils.command_line_utils import CommandLineUtils
import getpass
import time
import threading

bastion_topic = "message_topic"
remote_device_response_topic = "bastion/port"
cmdData = CommandLineUtils.parse_sample_input_pubsub()
received_all_event = threading.Event()
received_count = 0
# Define the range of ports to use
MIN_PORT = 12345
MAX_PORT = 65535

class PortPool:
    def __init__(self):
        self.available_ports = set(range(MIN_PORT, MAX_PORT + 1))

    def assign_port(self):
        if not self.available_ports:
            raise ValueError("No available ports in the pool")
        
        port = self.available_ports.pop()
        return port

    def release_port(self, port):
        if port < MIN_PORT or port > MAX_PORT:
            raise ValueError("Port is out of range")
        
        self.available_ports.add(port)

# Create an instance of the PortPool
port_pool = PortPool()

def on_message_received(topic, payload, **kwargs):
    print(f"Received message on topic '{topic}': {payload}")

    if topic == bastion_topic:
        time.sleep(0.5)
        handle_bastion_request(payload)
    global received_count
    received_count += 1
    if received_count == cmdData.input_count:
        received_all_event.set()

def handle_bastion_request(payload):
    try:
        data = json.loads(payload)
        pi_id = data.get("pi_id")

        if authenticate_client(pi_id):
            port = assign_port()
            send_port_to_remote_device(pi_id, port)
    except json.JSONDecodeError:
        print("Error decoding JSON payload")

def authenticate_client(pi_id):
    return True  

def assign_port():
    return port_pool.assign_port()

def send_port_to_remote_device(pi_id, port):
    port_assignment_message = {"pi_id": pi_id, "port": port}
    mqtt_connection.publish(
        topic=remote_device_response_topic,
        payload=json.dumps(port_assignment_message),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    print(f"Assigned port {port} for client {pi_id}")

def on_connect_success():
    print("Connected to AWS IoT Core")
    mqtt_connection.subscribe(
        topic=bastion_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received
    )
    print(f"Subscribed to topic: {bastion_topic}")
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
 
def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    print("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))
    # Callback when a connection attempt fails
def on_connection_failure(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionFailureData)
    print("Connection failed with error code: {}".format(callback_data.error))

# Callback when a connection has been disconnected or shutdown successfully
def on_connection_closed(connection, callback_data):
    print("Connection closed")
def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))
if __name__ == "__main__":
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

