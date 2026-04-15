import socket
import threading
import json
import time
import os
import urllib.request
from emp_crypto import x_pulse_hash

class EMPNetwork:
    """
    Protocole 'Echo-Mesh Propagation' (EMP) v2.
    Full UDP P2P - Sans serveur - NAT Traversal via Gossip & Flooding.
    """
    
    def __init__(self, friend_code: str, port: int = 42424):
        self.friend_code = friend_code
        self.port = port
        self.peers = {} # { (ip, port): last_seen }
        self.routing_table = {} # { friend_code_hash: (ip, port, timestamp) }
        self.messages_seen = set()
        self.on_message_received = None
        self.running = True
        self.public_ip = "127.0.0.1"
        
        self.my_address_hash = x_pulse_hash(friend_code.encode()).hex()
        
        # Socket UDP unique pour tout (Ecoute + Envoi)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("0.0.0.0", self.port))
        except:
            self.port = 42425 + (int(time.time()) % 100)
            self.sock.bind(("0.0.0.0", self.port))

        # Threads
        threading.Thread(target=self._discover_public_ip, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        threading.Thread(target=self._udp_beacon, daemon=True).start()
        threading.Thread(target=self._gossip_loop, daemon=True).start()
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def _discover_public_ip(self):
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
                self.public_ip = response.read().decode('utf-8')
        except: pass

    def _listen_loop(self):
        """Boucle d'écoute UDP unique."""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                packet = json.loads(data.decode())
                self._handle_packet(packet, addr)
            except: continue

    def _handle_packet(self, packet, addr):
        packet_id = packet.get("id")
        if packet_id in self.messages_seen: return
        self.messages_seen.add(packet_id)
        
        sender_code = packet.get("sender_code")
        msg_type = packet.get("type")
        
        # Mise à jour des pairs et de la table de routage
        self.peers[addr] = time.time()
        if sender_code:
            s_hash = x_pulse_hash(sender_code.encode()).hex()
            # On stocke l'IP d'où vient le message pour ce code ami
            self.routing_table[s_hash] = (addr[0], addr[1], time.time())

        # Traitement par type
        if msg_type == "gossip_sync":
            remote_table = packet.get("content", {})
            for f_hash, info in remote_table.items():
                if f_hash != self.my_address_hash:
                    ip, port, ts = info
                    # On ne met à jour que si l'info est plus récente
                    if f_hash not in self.routing_table or ts > self.routing_table[f_hash][2]:
                        self.routing_table[f_hash] = (ip, port, ts)
                        # On "punch" vers le nouveau pair découvert pour ouvrir le NAT
                        self._send_raw({"type": "punch", "sender_code": self.friend_code}, (ip, port))
            return
        
        if msg_type == "punch":
            # Juste pour ouvrir le NAT et mettre à jour la routing_table
            return

        dest_hash = packet.get("dest_hash")
        if dest_hash == self.my_address_hash or dest_hash == "broadcast":
            if self.on_message_received:
                self.on_message_received(packet)
        
        # Relais (Flooding intelligent)
        if packet.get("ttl", 0) > 0:
            packet["ttl"] -= 1
            self._relay_packet(packet, exclude_addr=addr)

    def _send_raw(self, packet, addr):
        try:
            if "id" not in packet: packet["id"] = x_pulse_hash(os.urandom(8)).hex()
            data = json.dumps(packet).encode()
            self.sock.sendto(data, addr)
        except: pass

    def _relay_packet(self, packet, exclude_addr=None):
        """Relaye le paquet à tous les pairs connus + destination directe."""
        dest_hash = packet.get("dest_hash")
        data = json.dumps(packet).encode()
        
        # 1. Envoi direct à la destination si connue
        if dest_hash in self.routing_table:
            target_addr = (self.routing_table[dest_hash][0], self.routing_table[dest_hash][1])
            if target_addr != exclude_addr:
                try: self.sock.sendto(data, target_addr)
                except: pass

        # 2. Inondation aux voisins (Mesh)
        for addr in list(self.peers.keys()):
            if addr != exclude_addr:
                try: self.sock.sendto(data, addr)
                except: pass

    def send_pulse(self, dest_friend_code: str, content: str, msg_type: str = "text"):
        dest_hash = x_pulse_hash(dest_friend_code.encode()).hex() if dest_friend_code != "broadcast" else "broadcast"
        packet = {
            "id": x_pulse_hash(os.urandom(32)).hex(),
            "sender_code": self.friend_code,
            "dest_hash": dest_hash,
            "type": msg_type,
            "content": content,
            "timestamp": time.time(),
            "ttl": 15 # TTL augmenté pour le mesh mondial
        }
        self.messages_seen.add(packet["id"])
        self._relay_packet(packet)

    def _udp_beacon(self):
        """Broadcast local pour trouver les gens sur le même Wi-Fi."""
        while self.running:
            try:
                packet = {
                    "type": "beacon",
                    "sender_code": self.friend_code,
                    "port": self.port,
                    "id": x_pulse_hash(os.urandom(8)).hex()
                }
                data = json.dumps(packet).encode()
                self.sock.sendto(data, ("255.255.255.255", 42424))
            except: pass
            time.sleep(10)

    def _gossip_loop(self):
        """Partage la table de routage et maintient les trous NAT ouverts."""
        while self.running:
            if self.peers or self.routing_table:
                sync_packet = {
                    "type": "gossip_sync",
                    "sender_code": self.friend_code,
                    "content": self.routing_table,
                    "id": x_pulse_hash(os.urandom(8)).hex()
                }
                # On envoie à tous les pairs actifs (Heartbeat)
                for addr in list(self.peers.keys()):
                    self._send_raw(sync_packet, addr)
                
                # On tente aussi de "re-puncher" les amis dans la table de routage
                for f_hash, info in list(self.routing_table.items()):
                    if f_hash != self.my_address_hash:
                        self._send_raw({"type": "punch", "sender_code": self.friend_code}, (info[0], info[1]))
            time.sleep(15)

    def _cleanup_loop(self):
        """Nettoie les pairs inactifs."""
        while self.running:
            now = time.time()
            for addr, last_seen in list(self.peers.items()):
                if now - last_seen > 60: # 1 minute sans signe de vie
                    del self.peers[addr]
            time.sleep(30)

    def connect_to_peer(self, ip, port=42424):
        """Tente d'initier une connexion (punch) avec une IP spécifique."""
        try:
            addr = (ip, int(port))
            packet = {
                "type": "punch",
                "sender_code": self.friend_code,
                "id": x_pulse_hash(os.urandom(8)).hex()
            }
            self._send_raw(packet, addr)
            self.peers[addr] = time.time()
            return True
        except: return False

    def stop(self):
        self.running = False
        self.sock.close()

if __name__ == "__main__":
    pass
