import streamlit as st
import socket
import requests
from datetime import datetime
import pytz
import pandas as pd
import re

# ===== Session State Initialization for Logging and Authentication =====
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ===== Helper Functions =====
def check_credentials(username, password):
    # Change credentials as needed
    return username == "admin" and password == "Sangwan@2002"

def log_activity(action, status, details):
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    st.session_state.logs.append({
        "Timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "Action": action,
        "Status": status,
        "Details": details
    })

def log_error(action, error_message):
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    st.session_state.errors.append({
        "Timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "Action": action,
        "Error": error_message
    })

def extract_data_from_format(data_format):
    """Extract IMEI, latitude, and longitude from a provided format string.
       Markers: '#<15-digit IMEI>#' and '#<lat>,N,' and ',N,<lon>,E,'"""
    try:
        imei = re.search(r'#(\d{15})#', data_format).group(1)
        lat = re.search(r'#(\d+\.\d+),N,', data_format).group(1)
        lon = re.search(r',N,(\d+\.\d+),E,', data_format).group(1)
        # Format lat and lon
        lat = f"{float(lat):09.6f}"
        lon = f"{float(lon):09.6f}"
        return imei, lat, lon
    except AttributeError:
        st.error('Invalid format. Please ensure the markers are correctly placed.')
        log_error("Extract Data", "Invalid format provided")
        return None, None, None

def send_tcp_packet(ip, port, packet):
    """Send a TCP packet using the socket module."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((ip, port))
            tcp_socket.sendall(packet.encode('utf-8'))
        return f"✅ TCP packet sent successfully!"
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

# ===== Endpoint Mappings (Hidden from the user) =====
# TCP endpoints for various states
tcp_endpoints = {
    "Chhattisgarh": {"ip": "164.100.64.209", "port": 6004},
    "Bihar": {"ip": "164.100.64.230", "port": 9031},
    "Uttarakhand": {"ip": "103.116.27.26", "port": 9999},
    "Chandigarh": {"ip": "164.100.64.250", "port": 9031},
    "Maharashtra": {"ip": "103.91.244.23", "port": 4030},
    "Jammu": {"ip": "164.52.220.32", "port": 2049},
}

# HTTP endpoints for manual data sender (for Kerala and West Bengal)
http_endpoints = {
    "Kerala": "http://103.135.130.119:80",
    "West Bengal": "http://117.221.20.174:80?vltdata",
}

# ===== Packet Template Functions for TCP =====
def build_tcp_packet(packet_type, state, imei, date, time_str, lat, lon):
    state_field = state.upper()
    if packet_type == "Packet 1":
        return (f"$NMP,{state_field},AIS01.1,IF,08,L,{imei},VRN_TMP22,1,{date},{time_str},"
                f"{lat},N,{lon},E,000.00,191.00,48,0611,0.61,0.39,airtel,0,1,25.4,4.0,0,"
                "C,30,404,90,18C3,E37BB66,-61,164,39150,-73,163,39150,x,x,x,x,x,x,0000,"
                "10,000001,0.0,0.0,0,(0,0,0)*120")
    elif packet_type == "Packet 2":
        return (f"$NMP,{state_field},AIS01.1,IF,08,L,{imei},VRN_TMP23,2,{date},{time_str},"
                f"{lat},N,{lon},E,001.00,192.00,48,0611,0.62,0.38,airtel,0,1,26.4,4.0,0,"
                "C,30,405,90,18C3,E37BB66,-62,165,39150,-74,163,39150,y,y,y,y,y,y,0001,"
                "11,000002,0.1,0.1,1,(1,1,1)*121")
    elif packet_type == "Packet 3":
        return (f"$NMP,{state_field},AIS01.1,IF,08,L,{imei},VRN_TMP24,3,{date},{time_str},"
                f"{lat},N,{lon},E,002.00,193.00,48,0611,0.63,0.37,airtel,0,1,27.4,4.0,0,"
                "C,30,406,90,18C3,E37BB66,-63,166,39150,-75,163,39150,z,z,z,z,z,z,0002,"
                "12,000003,0.2,0.2,2,(2,2,2)*122")
    else:
        return ""

# ===== Build HTTP Packet Function =====
def build_http_packet(imei, latitude, longitude):
    # Use current date/time in Asia/Kolkata timezone for HTTP packet
    delhi_tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(delhi_tz)
    date_str = now.strftime('%d%m%y')
    time_str = now.strftime('%H%M%S')
    # Adjust the packet format as needed; this is a sample structure.
    return (f"NRM{imei}01L1{date_str}{time_str}0{latitude}N0{longitude}E404x950D2900"
            "DC06A72000.00000.0053001811M0827.00airtel")

# ===== Main App =====
st.title("Complete Packet Sender Dashboard")

# ---------- Authentication ----------
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
    st.stop()

# ---------- Tabs for Functionality ----------
tab_tcp, tab_http, tab_logs = st.tabs(["TCP Packet Sender", "HTTP Manual Data Sender", "Activity Logs"])

# --- Tab 1: TCP Packet Sender ---
with tab_tcp:
    st.header("TCP Packet Sender (Endpoints Hidden)")
    state_tcp = st.selectbox("Select State (TCP)", list(tcp_endpoints.keys()))
    packet_type = st.selectbox("Select Packet Type", ["Packet 1", "Packet 2", "Packet 3"])
    
    # Input fields for packet parameters
    imei = st.text_input("IMEI (15 digits)", value="864568069809003", max_chars=15)
    date = st.text_input("Date (ddmmyyyy)", value="21122024", max_chars=8)
    time_str = st.text_input("Time (hhmmss)", value="062855", max_chars=6)
    lat = st.text_input("Latitude", value="20.0704536")
    lon = st.text_input("Longitude", value="73.9026718")
    
    if st.button("Send TCP Packet"):
        if len(imei) != 15 or not imei.isdigit():
            st.error("IMEI must be a 15-digit number.")
            log_error("TCP Packet Sender", f"Invalid IMEI: {imei}")
        else:
            # Build packet using the chosen template
            packet = build_tcp_packet(packet_type, state_tcp, imei, date, time_str, lat, lon)
            endpoint = tcp_endpoints[state_tcp]
            result = send_tcp_packet(endpoint["ip"], endpoint["port"], packet)
            if "✅" in result:
                st.success(result)
                log_activity("TCP Packet Sender", "Success", f"State: {state_tcp}, Type: {packet_type}")
            else:
                st.error(result)
                log_error("TCP Packet Sender", result)

# --- Tab 2: HTTP Manual Data Sender ---
with tab_http:
    st.header("HTTP Manual Data Sender")
    state_http = st.selectbox("Select State (HTTP)", list(http_endpoints.keys()))
    api_url = http_endpoints[state_http]
    st.write(f"Using API endpoint for {state_http}.")
    
    # Choose input method
    input_method = st.selectbox("Input Method", ["Manual Entry", "Extract from Format"])
    
    if input_method == "Manual Entry":
        imei_list = st.text_area("IMEIs (comma-separated, each 15 digits)")
        latitude = st.text_input("Latitude")
        longitude = st.text_input("Longitude")
    else:
        data_format = st.text_area("Data Format (include markers: '#<15-digit IMEI>#', '#<lat>,N,' and ',N,<lon>,E,')")
    
    if st.button("Send HTTP Data"):
        if input_method == "Extract from Format":
            imei_http, latitude, longitude = extract_data_from_format(data_format)
            if not imei_http or not latitude or not longitude:
                st.error("Failed to extract data from format.")
                log_activity("HTTP Data Sender", "Failed", "Extraction error")
                st.stop()
            imei_list = imei_http  # extraction mode: single IMEI
        else:
            imei_list = [x.strip() for x in imei_list.split(",") if x.strip()]
        
        for imei in (imei_list if isinstance(imei_list, list) else [imei_list]):
            if len(imei) != 15 or not imei.isdigit():
                st.error(f"IMEI must be a 15-digit number: {imei}")
                log_activity("HTTP Data Sender", "Failed", f"Invalid IMEI: {imei}")
                continue
            # Build HTTP packet using current timestamp
            packet_http = build_http_packet(imei, latitude, longitude)
            data_payload = {'vltdata': packet_http}
            result_http, response_content = send_http_data(api_url, data_payload)
            if "✅" in result_http:
                st.success(f"{result_http} for IMEI: {imei}")
                st.write(f"Packet Sent: {packet_http}")
                log_activity("HTTP Data Sender", "Success", f"IMEI: {imei}, Packet: {packet_http}")
                if response_content:
                    if isinstance(response_content, dict):
                        st.json(response_content)
                    else:
                        st.write(response_content)
            else:
                st.error(f"HTTP data send failed for IMEI: {imei}")
                log_error("HTTP Data Sender", f"IMEI: {imei}, Error: {result_http}")

# --- Tab 3: Activity & Error Logs ---
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
