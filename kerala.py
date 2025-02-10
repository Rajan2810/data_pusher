import streamlit as st
import socket
import requests
from datetime import datetime
import pytz
import pandas as pd
import re

# ----- Session State Initialization for Logging -----
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ----- Helper Functions -----
def check_credentials(username, password):
    return username == "admin" and password == "Sangwan@2002"

def log_activity(action, status, details):
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    log_entry = {
        "Timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "Action": action,
        "Status": status,
        "Details": details
    }
    st.session_state.logs.append(log_entry)

def log_error(action, error_message):
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    error_entry = {
        "Timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "Action": action,
        "Error": error_message
    }
    st.session_state.errors.append(error_entry)

def extract_data_from_format(data_format):
    """Extract IMEI, latitude, and longitude from a given format string."""
    try:
        imei = re.search(r'#(\d{15})#', data_format).group(1)
        lat = re.search(r'#(\d+\.\d+),N,', data_format).group(1)
        long = re.search(r',N,(\d+\.\d+),E,', data_format).group(1)
        lat = f"{float(lat):09.6f}"
        long = f"{float(long):09.6f}"
        return imei, lat, long
    except AttributeError:
        st.error('Invalid format. Please ensure the format is correct.')
        log_error("Extract Data", "Invalid format")
        return None, None, None

def send_tcp_packet(ip, port, packet):
    """Send a TCP packet using the socket module."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((ip, port))
            tcp_socket.sendall(packet.encode('utf-8'))
        return f"✅ TCP packet sent to {ip}:{port} successfully!"
    except Exception as e:
        return f"❌ Error sending TCP packet: {e}"

def send_http_data(api_url, data):
    """Send data via HTTP POST request."""
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(api_url, data=data, headers=headers)
        response.raise_for_status()
        try:
            response_json = response.json()
            return f"✅ HTTP data sent successfully!", response_json
        except ValueError:
            return f"✅ HTTP data sent successfully!", response.text
    except requests.exceptions.RequestException as e:
        return f"❌ HTTP request failed: {e}", None

# ----- Mappings for Endpoints and Default Packets -----
# TCP endpoints for states (these states have distinct IP/port and packet structure)
tcp_states = {
    "Chhattisgarh": {"ip": "164.100.64.209", "port": 6004},
    "Bihar": {"ip": "164.100.64.230", "port": 9031},
    "Uttarakhand": {"ip": "103.116.27.26", "port": 9999},
    "Chandigarh": {"ip": "164.100.64.250", "port": 9031},
    "Maharashtra": {"ip": "103.91.244.23", "port": 4030},
    "Jammu": {"ip": "164.52.220.32", "port": 2049},
}

# HTTP endpoints for manual data sender (for Kerala, West Bengal, etc.)
http_states = {
    "Kerala": "http://103.135.130.119:80",
    "West Bengal": "http://117.221.20.174:80?vltdata",
    # Add more if needed
}

# ----- Main App -----
st.title('Modified Packet Sender Dashboard')

# ----- Authentication -----
if not st.session_state.logged_in:
    st.subheader("Please Login")
    username = st.text_input('Username')
    password = st.text_input('Password', type='password')
    if st.button('Login'):
        if check_credentials(username, password):
            st.session_state.logged_in = True
            st.success('Login successful!')
            log_activity("Login", "Success", f"User {username} logged in.")
        else:
            st.error('Invalid credentials')
            log_activity("Login", "Failed", f"Invalid login attempt for {username}.")
    st.stop()  # Stop further execution until login is successful

# ----- Tabs for Different Functionalities -----
tab_tcp, tab_http, tab_logs = st.tabs(["TCP Packet Sender", "HTTP Manual Data Sender", "Activity Logs"])

# ---- Tab 1: TCP Packet Sender for Specific States ----
with tab_tcp:
    st.header("TCP Packet Sender")
    state_tcp = st.selectbox("Select State (TCP)", list(tcp_states.keys()))
    
    # Set default IP/port based on selection; allow override if needed.
    default_tcp = tcp_states[state_tcp]
    ip_tcp = st.text_input("Target IP", value=default_tcp["ip"])
    port_tcp = st.number_input("Target Port", min_value=1, max_value=65535, value=default_tcp["port"])
    
    # Generate a default packet structure for the selected state.
    default_packet_tcp = (f"$NMP,{state_tcp.upper()},AIS01.1,IF,08,L,864568069809003,VRN_TMP22,"
                          "1,21122024,062855,20.0704536,N,73.9026718,E,000.00,191.00,48,0611,"
                          "0.61,0.39,airtel,0,1,25.4,4.0,0,C,30,404,90,18C3,E37BB66,"
                          " -61,164,39150,-73,163,39150,x,x,x,x,x,x,0000,10,000001,0.0,0.0,0,(0,0,0)*120")
    
    packet_tcp = st.text_area("Packet Data (TCP)", value=default_packet_tcp, height=150)
    
    if st.button("Send TCP Packet"):
        result_tcp = send_tcp_packet(ip_tcp, port_tcp, packet_tcp)
        if "✅" in result_tcp:
            st.success(result_tcp)
            log_activity("TCP Packet Sender", "Success", f"State: {state_tcp}, IP: {ip_tcp}, Port: {port_tcp}")
        else:
            st.error(result_tcp)
            log_error("TCP Packet Sender", result_tcp)

# ---- Tab 2: HTTP Manual Data Sender for Other States ----
with tab_http:
    st.header("HTTP Manual Data Sender")
    state_http = st.selectbox("Select State (HTTP)", list(http_states.keys()))
    manual_api_url = http_states[state_http]
    st.write(f"Using API URL: {manual_api_url}")
    
    # Choose input method for packet details.
    input_method = st.selectbox("Input Method", ["Manual Entry", "Extract from Format"])
    
    if input_method == "Manual Entry":
        imei_list = st.text_area("IMEIs (comma-separated, each 15 digits)")
        latitude = st.text_input("Latitude")
        longitude = st.text_input("Longitude")
    else:
        data_format = st.text_area("Data Format (include #IMEI#, #lat,N, and ,N,long,E, markers)")
    
    if st.button("Send HTTP Data"):
        if input_method == "Extract from Format":
            imei_http, latitude, longitude = extract_data_from_format(data_format)
            if not imei_http or not latitude or not longitude:
                st.error("Failed to extract data from format.")
                log_activity("HTTP Data Sender", "Failed", "Extraction error")
                st.stop()
            imei_list = imei_http  # In extraction mode, we assume a single IMEI.
        else:
            imei_list = [x.strip() for x in imei_list.split(",") if x.strip()]
        
        for imei in (imei_list if isinstance(imei_list, list) else [imei_list]):
            if len(imei) != 15 or not imei.isdigit():
                st.error(f"IMEI must be a 15-digit number: {imei}")
                log_activity("HTTP Data Sender", "Failed", f"Invalid IMEI: {imei}")
                continue
            
            # Get current date and time (Asia/Kolkata timezone)
            delhi_tz = pytz.timezone('Asia/Kolkata')
            now = datetime.now(delhi_tz)
            date_str = now.strftime('%d%m%y')
            time_str = now.strftime('%H%M%S')
            
            # Format the packet (you may modify the format as needed)
            packet_http = (f"NRM{imei}01L1{date_str}{time_str}0{latitude}N0{longitude}E404x950D2900"
                           "DC06A72000.00000.0053001811M0827.00airtel")
            data_payload = {'vltdata': packet_http}
            result_http, response_content = send_http_data(manual_api_url, data_payload)
            if "✅" in result_http:
                st.success(f"{result_http} for IMEI: {imei}")
                st.write(f"Packet Sent: {packet_http}")
                log_activity("HTTP Data Sender", "Success", f"IMEI: {imei}, Packet: {packet_http}")
                if response_content:
                    st.json(response_content) if isinstance(response_content, dict) else st.write(response_content)
            else:
                st.error(f"HTTP data send failed for IMEI: {imei}")
                log_error("HTTP Data Sender", f"IMEI: {imei}, Error: {result_http}")

# ---- Tab 3: Activity Logs ----
with tab_logs:
    st.header("Activity & Error Logs")
    if st.session_state.logs:
        df_logs = pd.DataFrame(st.session_state.logs)
        st.subheader("Activity Logs")
        st.dataframe(df_logs)
        csv_logs = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button("Download Activity Logs (CSV)", data=csv_logs, file_name='activity_logs.csv', mime='text/csv')
        text_logs = df_logs.to_string(index=False)
        st.download_button("Download Activity Logs (Text)", data=text_logs, file_name='activity_logs.txt', mime='text/plain')
    else:
        st.info("No activity logs yet.")

    if st.session_state.errors:
        df_errors = pd.DataFrame(st.session_state.errors)
        st.subheader("Error Logs")
        st.dataframe(df_errors)
        csv_errors = df_errors.to_csv(index=False).encode('utf-8')
        st.download_button("Download Error Logs (CSV)", data=csv_errors, file_name='error_logs.csv', mime='text/csv')
        text_errors = df_errors.to_string(index=False)
        st.download_button("Download Error Logs (Text)", data=text_errors, file_name='error_logs.txt', mime='text/plain')
    else:
        st.info("No error logs yet.")
