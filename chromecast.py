import socket as socket
import ssl as ssl
import re as re
import time as time
import json as json
from struct import unpack
from select import poll, POLLIN, POLLHUP


INIT_MSGS = (b'\x00\x00\x00Y\x08\x00\x12\x08sender-0\x1a\nreceiver-0"(urn:x-cast:com.google.cast.tp.connection(\x002\x13{"type": "CONNECT"}',
             b'\x00\x00\x00g\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002&{"type": "GET_STATUS", "requestId": 1}'
             )

STATUS_MSG = b'\x00\x00\x00g\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002&{"type": "GET_STATUS", "requestId": $$$}'

VOL_MSGS = {4: b'\x00\x00\x00\x81\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002@{"type": "SET_VOLUME", "volume": {"XXCTRLXX": ###}, "requestId": $$$}',
            5: b'\x00\x00\x00\x82\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002A{"type": "SET_VOLUME", "volume": {"XXCTRLXX": ###}, "requestId": $$$}',
            6: b'\x00\x00\x00\x83\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002B{"type": "SET_VOLUME", "volume": {"XXCTRLXX": ###}, "requestId": $$$}',
            7: b'\x00\x00\x00\x84\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002C{"type": "SET_VOLUME", "volume": {"XXCTRLXX": ###}, "requestId": $$$}',
            8: b'\x00\x00\x00\x85\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002D{"type": "SET_VOLUME", "volume": {"XXCTRLXX": ###}, "requestId": $$$}'}


STOP_MSGS = {1: b'\x00\x00\x00\x96\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002U{"type": "STOP", "requestId": $$$, "sessionId": "###"}',
             2: b'\x00\x00\x00\x97\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002V{"type": "STOP", "requestId": $$$, "sessionId": "###"}',
             3: b'\x00\x00\x00\x98\x08\x00\x12\x08sender-0\x1a\nreceiver-0"#urn:x-cast:com.google.cast.receiver(\x002W{"type": "STOP", "requestId": $$$, "sessionId": "###"}'}


class Chromecast(object):
    def __init__(self, ip):
        self.ip = ip
        self.request = 2
        self.vol = 0  # an int between 0 and 100
        self.muted = False

        self.sess_id = 0
        self.connected = False
        self.poller = None

        self.connect()
        if not self.connected:
            print("Failed to connect to Chromecast on ", self.ip)

    def connect(self):
        print("Chromecast.connect()")
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.ip, 8009))
        self.s = ssl.wrap_socket(self.s)
        self.s.setblocking(False)
        self.poller = poll()
        self.poller.register(self.s, POLLIN)

        for msg in INIT_MSGS:
            # print(msg)
            # self.s.write(msg)
            self.write_message(msg)
        self.check_response(1)
        self.connected = True
        print("Connected to CHROMECAST on", self.ip)

    @property
    def get_volume(self):
        return int(self.vol * 100)

    def __repr__(self):
        return "Chromecast Object on IP {:s}".format(self.ip)

    def write_message(self, message):
        """Write a message to the socket"""

        # print("Writing message", message)
        self.s.write(message)

    def set_volume(self, volume):
        print("\n Set Volume ", volume)
        if volume < 0:
            volume = 0

        if volume > 100:
            volume = 100

        volume = "{:1.2f}".format(volume / 100.)

        print("Setting Vol to ", volume)
        msg_len = len(volume) + len(str(self.request))
        r_volmsg = VOL_MSGS[msg_len]
        r_volmsg = r_volmsg.replace(b'###', bytes(volume, 'utf-8'))
        r_volmsg = r_volmsg.replace(b'$$$', bytes(str(self.request), 'utf-8'))
        r_volmsg = r_volmsg.replace(b'XXCTRLXX', bytes('level', 'utf-8'))

        self.write_message(r_volmsg)
        self.check_response(self.request)
        self.request += 1

    def get_status(self):
        print("\n GetStatus")
        r_statusmsg = STATUS_MSG
        r_statusmsg = r_statusmsg.replace(b'$$$', bytes(str(self.request), 'utf-8'))
        self.s.write(r_statusmsg)
        # self.read_message()
        self.check_response(self.request)
        self.request += 1

    def disconnect(self):
        # Tidy up the poller then close the socket
        print("Disconnecting")
        self.poller.unregister(self.s)
        self.poller = None
        self.s.close()

    def toggle_mute(self):
        print("\n Toggle Mute")
        muted = self.muted
        if muted:
            mutestr = "false"
        else:
            mutestr = "true"
        msg_len = len(mutestr) + len(str(self.request))
        r_volmsg = VOL_MSGS[msg_len]
        r_volmsg = r_volmsg.replace(b'###', bytes(mutestr, 'utf-8'))
        r_volmsg = r_volmsg.replace(b'$$$', bytes(str(self.request), 'utf-8'))
        r_volmsg = r_volmsg.replace(b'XXCTRLXX', bytes('muted', 'utf-8'))
        print("mut msg", r_volmsg)

        self.write_message(r_volmsg)
        self.check_response(self.request)

        self.request += 1

        # self.get_status()

    def check_response(self, targetId):
        skt = self.s
        pol = self.poller
        while True:
            obj = pol.poll(200)
            if not obj:
                # Break out of the read cycle if the timeout is reached
                print("Poll reached timeout")
                break
            if obj[0][1] & POLLHUP:
                self.disconnect()
                self.connect()
                skt = self.s
                pol = self.poller
                continue
            hdr = skt.read(4)
            # print("Poll object", obj, hdr)

            # If the header contains data, we have a packet, if not port
            # just "non-blocking" returned.
            if hdr is not None:
                if len(hdr) > 0:
                    # Get the payload size and read it
                    siz = unpack('>I', hdr)[0]
                    msg = str(skt.read(siz))
                    # print("message", msg)
                    # Extract the requestId
                    if "requestId" in msg:
                        requestId = int(re.search('\"requestId\":([0-9]*)', msg).group(1))  # "requestId":12,
                    else:
                        requestId = 0
                    print("Target:", targetId, "    Request:", requestId)
                    if requestId >= 0:
                        self.process_messages(msg)
                        if requestId == targetId:
                            # No need to wait for any more messages
                            break
            # time.sleep_ms(100)
        print("Finished reading messages")

    def _read_socket_byte(self, nbytes):
        """Read some bytes from the socket."""
        chunks = []
        bytes_recv = 0
        while bytes_recv < nbytes:
            try:
                chunk = self.s.read(min(nbytes - bytes_recv, 2048))  # Don't
                if chunk == b"":
                    raise socket.error("no data in socket, socket connection broken")
                chunks.append(chunk)
                bytes_recv += len(chunk)
            except socket.timeout:
                continue
            except OSError as exc:
                if exc.message in ("The handshake operation timed out",
                                   "The write operation timed out",
                                   "The read operation timed out"
                                   ):
                    continue
                raise
        return b"".join(chunks)

    def read_message(self):
        skt = self.s
        pol = poll()
        pol.register(skt, POLLIN)
        while True:
            obj = pol.poll(100)
            if not obj:
                # Break out of the read cycle if the timeout is reached
                print("Poll reached timeout")
                break
            print("Poll object", obj)

            if obj[0][0] | POLLHUP:
                break
            hdr = skt.read(4)

            if hdr is not None:
                if len(hdr) > 0:
                    print("Header", hdr)
                    siz = unpack('>I', hdr)[0]
                    # print(f"Receieved header {siz}")
                    msg = str(skt.read(siz))
                    self.process_messages(msg)
            time.sleep_ms(100)
        print("Finished reading messages")

    def process_messages(self, msg):

        # print("Receieved", msg)
        if '"type":"RECEIVER_STATUS"' in msg:
            print("Processing Message - status")
            js_str = msg[msg.find(r'requestId') - 2:-1]
            msg_key = 'status'
            # self.process_status(msg)
            # self.process_json(js_str)
        elif '"type":"DEVICE_UPDATED"' in msg:
            print("Processing Message - dev_update")
            js_str = msg[msg.find(r'"device"') - 1:-1]
            msg_key = 'device'
            # self.process_dev_update(msg)
        else:
            print("Recieved message", msg)
            return
        self.process_json(js_str, msg_key)

    def process_json(self, js_str, msg_key):
        try:
            js = json.loads(js_str)
            # print(json.dumps(js, indent=2))
            try:
                vol = js[msg_key]['volume']['level']
                self.vol = int(vol * 100)
            except KeyError:
                print("Can't find volume level in JSON structure", js_str)
            try:
                mut = js[msg_key]['volume']['muted']
                print("Muted value ", mut)
                self.muted = mut
            except KeyError:
                print("Can't find volume level in JSON structure", js_str)

        except json.JSONDecodeError:
            print("Error decoding JSON message", js_str)
        print("Reciever Status contained vol", vol)
        return
