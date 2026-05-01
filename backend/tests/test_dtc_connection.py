"""
Test DTC Protocol Connection to Sierra Chart
Verifies the protocol version fix and encoding request
"""
import asyncio
import socket
import struct
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_feed.dtc_protocol import (
    EncodingRequest, LogonRequest, parse_header,
    DTC_MSG, DTC_VERSION, ENCODING_VARIABLE_LENGTH_STRINGS
)

class DTCConnectionTest:
    def __init__(self, host="127.0.0.1", port=11099):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        
    async def connect(self):
        """Establish TCP connection to Sierra Chart"""
        try:
            print(f"[TEST] Connecting to {self.host}:{self.port}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"[OK] [TEST] TCP connection established")
            return True
        except Exception as e:
            print(f"[FAIL] [TEST] Connection failed: {e}")
            return False
    
    async def send_encoding_request(self):
        """Send encoding request with protocol version 8"""
        try:
            req = EncodingRequest(encoding=ENCODING_VARIABLE_LENGTH_STRINGS)
            data = req.pack()
            
            print(f"\n[TEST] Sending EncodingRequest:")
            print(f"  - Protocol Version: {DTC_VERSION}")
            print(f"  - Encoding Type: {ENCODING_VARIABLE_LENGTH_STRINGS} (VLS)")
            print(f"  - Message Size: {len(data)} bytes")
            print(f"  - Raw bytes: {data.hex()}")
            
            self.socket.sendall(data)
            print(f"[OK] [TEST] EncodingRequest sent")
            
            # Wait for response
            response = await self.receive_message()
            if response:
                size, msg_type = parse_header(response)
                if msg_type == DTC_MSG.ENCODING_RESPONSE:
                    print(f"[OK] [TEST] Received ENCODING_RESPONSE (type {msg_type})")
                    return True
                else:
                    print(f"⚠️ [TEST] Unexpected response type: {msg_type}")
                    return False
            return False
            
        except Exception as e:
            print(f"[FAIL] [TEST] EncodingRequest failed: {e}")
            return False
    
    async def send_logon_request(self):
        """Send logon request"""
        try:
            req = LogonRequest(username="TestAgent", password="", heartbeat_interval=60)
            data = req.pack(is_vls=True)  # Use VLS encoding to match our encoding request
            
            print(f"\n[TEST] Sending LogonRequest:")
            print(f"  - Protocol Version: {req.ProtocolVersion}")
            print(f"  - Username: {req.Username}")
            print(f"  - Heartbeat Interval: {req.HeartbeatInterval}s")
            print(f"  - Encoding: VLS")
            print(f"  - Message Size: {len(data)} bytes")
            
            self.socket.sendall(data)
            print(f"[OK] [TEST] LogonRequest sent")
            
            # Wait for response
            response = await self.receive_message()
            if response:
                size, msg_type = parse_header(response)
                if msg_type == DTC_MSG.LOGON_RESPONSE:
                    # Parse result code (int32 at offset 4 in body, offset 8 total)
                    result_code = struct.unpack("<i", response[8:12])[0]
                    
                    # Try to parse ResultText (VLS string at offset 12)
                    result_text = ""
                    try:
                        text_len = struct.unpack("<I", response[12:16])[0]
                        if text_len > 0 and text_len < 1000:
                            result_text = response[16:16+text_len].decode('ascii', errors='ignore')
                    except:
                        pass
                    
                    print(f"\n[OK] [TEST] Received LOGON_RESPONSE (type {msg_type})")
                    print(f"  - Result Code: {result_code}")
                    if result_text:
                        print(f"  - Result Text: {result_text}")
                    
                    if result_code == 1:
                        print(f"[SUCCESS] [TEST] LOGON ACCEPTED! Connection successful!")
                        return True
                    else:
                        print(f"[FAIL] [TEST] LOGON REJECTED with code {result_code}")
                        # Common error codes:
                        # 1 = Success
                        # 2 = Error
                        # 3 = Error - No reconnect
                        # 4 = Reconnect to new address
                        # 8 = Unknown (check ResultText)
                        return False
                else:
                    print(f"⚠️ [TEST] Unexpected response type: {msg_type}")
                    return False
            return False
            
        except Exception as e:
            print(f"[FAIL] [TEST] LogonRequest failed: {e}")
            return False
    
    async def receive_message(self):
        """Receive a DTC message"""
        try:
            # Read header first (4 bytes)
            header = b''
            while len(header) < 4:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, self.socket.recv, 4 - len(header)
                )
                if not chunk:
                    return None
                header += chunk
            
            size, msg_type = parse_header(header)
            
            # Read rest of message
            body = b''
            remaining = size - 4
            while len(body) < remaining:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, self.socket.recv, remaining - len(body)
                )
                if not chunk:
                    return None
                body += chunk
            
            return header + body
            
        except Exception as e:
            print(f"[FAIL] [TEST] Receive failed: {e}")
            return None
    
    def disconnect(self):
        """Close connection"""
        if self.socket:
            self.socket.close()
            print(f"\n[TEST] Connection closed")

async def main():
    """Run the DTC connection test"""
    print("=" * 70)
    print("DTC PROTOCOL CONNECTION TEST")
    print("=" * 70)
    
    test = DTCConnectionTest(host="127.0.0.1", port=11099)
    
    # Step 1: Connect
    if not await test.connect():
        print("\n[FAIL] TEST FAILED: Could not establish TCP connection")
        return False
    
    # Step 2: Send encoding request
    if not await test.send_encoding_request():
        print("\n[FAIL] TEST FAILED: Encoding request rejected")
        test.disconnect()
        return False
    
    # Step 3: Send logon request
    if not await test.send_logon_request():
        print("\n[FAIL] TEST FAILED: Logon rejected")
        test.disconnect()
        return False
    
    # Success!
    print("\n" + "=" * 70)
    print("[SUCCESS] ALL TESTS PASSED!")
    print("=" * 70)
    print("\nThe DTC protocol fix is working correctly:")
    print("  [OK] Protocol version 8 is being sent")
    print("  [OK] VLS encoding (type 6) is accepted")
    print("  [OK] Logon is successful")
    print("\nYou can now run the full system with confidence!")
    
    test.disconnect()
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
