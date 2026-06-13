"""
Cliente RCON para comunicación con servidor Minecraft.
Permite enviar comandos y recibir respuestas en tiempo real.
"""

import socket
import struct

class RCONClient:
    def __init__(self, host='localhost', port=25575, password='minecolab_panel'):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self.request_id = 0

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))

            self.request_id += 1
            auth_id = self.request_id

            self._send_packet(auth_id, 3, self.password)

            resp_id, resp_type, resp_payload = self._receive_packet()

            if resp_id != auth_id and resp_id != -1:
                resp_id, resp_type, resp_payload = self._receive_packet()

            if resp_id == auth_id:
                return True
            else:
                self.disconnect()
                return False
        except Exception as e:
            print(f"[RCON] Error conectando: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def send_command(self, command: str) -> str:
        if not self.is_connected():
            if not self.connect():
                raise OSError("No se pudo conectar al servidor RCON")

        try:
            self.request_id += 1
            cmd_id = self.request_id

            self._send_packet(cmd_id, 2, command)

            resp_id, resp_type, resp_payload = self._receive_packet()

            return resp_payload.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"[RCON] Error enviando comando: {e}")
            self.disconnect()
            raise OSError(f"Error de comunicación RCON: {e}")

    def is_connected(self) -> bool:
        return self.socket is not None

    def _send_packet(self, req_id: int, packet_type: int, payload: str):
        payload_bytes = payload.encode('utf-8')
        length = 10 + len(payload_bytes)
        packet = struct.pack('<iii', length, req_id, packet_type) + payload_bytes + b'\x00\x00'
        self.socket.sendall(packet)

    def _receive_packet(self):
        header = self.socket.recv(4)
        if not header or len(header) < 4:
            raise OSError("Conexión cerrada o cabecera incompleta")
        length = struct.unpack('<i', header)[0]

        data = b""
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise OSError("Conexión cerrada durante la lectura del payload")
            data += chunk

        req_id, packet_type = struct.unpack('<ii', data[:8])
        payload = data[8:-2]
        return req_id, packet_type, payload
