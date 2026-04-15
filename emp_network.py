import socket
import threading
import json
import time
import os
import urllib.request
from emp_crypto import x_pulse_hash

class EMPNetwork:
    """
    Protocole 'Echo-Mesh Propagation' (EMP).
    Découverte automatique UDP + Relais de messages Mesh + Gossip Global.
    """
    
    def __init__(self, friend_code: str, port: int = 42424):
        self.friend_code = friend_code
        self.port = port
        self.peers = {} # {ip: socket}
        self.known_peer_addresses = set() # { (ip, port) }
        self.messages_seen = set() # Pour éviter les boucles de relais
        self.on_message_received = None # Callback (packet)
        self.running = True
        self.public_ip = "127.0.0.1"
        
        # On calcule le hash de notre code ami (notre adresse dans le mesh)
        self.my_address_hash = x_pulse_hash(friend_code.encode()).hex()
        
        # Tentative de récupération de l'IP publique (pour le mesh global)
        threading.Thread(target=self._discover_public_ip, daemon=True).start()

        # Serveur TCP pour les messages du mesh
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(10)
        except:
            self.port = 42425 + (int(time.time()) % 100)
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(10)
            
        threading.Thread(target=self._accept_connections, daemon=True).start()
        threading.Thread(target=self._udp_beacon, daemon=True).start()
        threading.Thread(target=self._udp_listener, daemon=True).start()
        # Thread de Gossip périodique pour maintenir le réseau mondial
        threading.Thread(target=self._gossip_loop, daemon=True).start()

    def _discover_public_ip(self):
        """Récupère l'IP publique via un service tiers gratuit (standard en P2P)."""
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
                self.public_ip = response.read().decode('utf-8')
        except: pass
        # Une fois l'IP connue, on tente d'ouvrir le port sur la box (UPnP)
        threading.Thread(target=self._try_upnp, daemon=True).start()

    def _try_upnp(self):
        """Tente d'ouvrir le port via UPnP (Sans bibliothèque externe)."""
        # On tente de trouver la gateway (souvent .1 ou .254)
        local_ip = socket.gethostbyname(socket.gethostname())
        gw_prefix = ".".join(local_ip.split(".")[:-1])
        gateways = [f"{gw_prefix}.1", f"{gw_prefix}.254"]
        
        for gw in gateways:
            try:
                # On tente d'envoyer une requête SOAP standard UPnP à l'adresse par défaut
                # (Certains routeurs écoutent sur 1900 ou 5000)
                pass # L'implémentation complète sans lib est complexe et risquée ici
                # On va se concentrer sur le fait que si UN SEUL a un port ouvert, ça marche.
            except: pass

    def _gossip_loop(self):
        """Partage périodiquement la liste des pairs connus pour l'expansion du mesh."""
        while self.running:
            if self.peers:
                # On prépare un paquet de type "peers_list"
                peers_data = list(self.known_peer_addresses)
                self.send_pulse("broadcast", peers_data, "peers_gossip")
            time.sleep(30) # Toutes les 30 secondes

    def _udp_beacon(self):
        """Envoie un signal de présence sur le réseau local."""
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            try:
                msg = json.dumps({"type": "beacon", "port": self.port}).encode()
                udp.sendto(msg, ("255.255.255.255", 42424))
            except: pass
            time.sleep(5)

    def _udp_listener(self):
        """Écoute les signaux de présence des autres nœuds sur le LAN."""
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            udp.bind(("0.0.0.0", 42424))
        except: return
        
        while self.running:
            try:
                data, addr = udp.recvfrom(1024)
                info = json.loads(data.decode())
                if info.get("type") == "beacon":
                    remote_ip = addr[0]
                    remote_port = info.get("port")
                    if remote_ip not in self.peers:
                        threading.Thread(target=self.connect_to_peer, args=(remote_ip, remote_port), daemon=True).start()
            except: pass

    def _accept_connections(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_peer, args=(client_sock, addr), daemon=True).start()
            except: break

    def _handle_peer(self, sock, addr):
        ip = addr[0]
        self.peers[ip] = sock
        # On ajoute l'adresse aux pairs connus (en supposant le port par défaut si non spécifié)
        self.known_peer_addresses.add((ip, self.port))
        
        while self.running:
            try:
                data = sock.recv(65535)
                if not data: break
                
                raw_str = data.decode()
                for part in raw_str.split('}{'):
                    if not part.startswith('{'): part = '{' + part
                    if not part.endswith('}'): part = part + '}'
                    
                    try:
                        packet = json.loads(part)
                    except:
                        continue
                    
                    packet_id = packet.get("id")
                    if packet_id in self.messages_seen: continue
                    self.messages_seen.add(packet_id)
                    
                    msg_type = packet.get("type")
                    
                    # Gestion spéciale du Gossip pour étendre le réseau
                    if msg_type == "peers_gossip":
                        new_peers = packet.get("content", [])
                        for p_ip, p_port in new_peers:
                            if p_ip != self.public_ip and p_ip != "127.0.0.1":
                                if (p_ip, p_port) not in self.known_peer_addresses:
                                    threading.Thread(target=self.connect_to_peer, args=(p_ip, p_port), daemon=True).start()
                        continue # Pas besoin de relayer le gossip tel quel, on le fait via notre propre loop

                    dest_hash = packet.get("dest_hash")
                    if dest_hash == self.my_address_hash or dest_hash == "broadcast":
                        if self.on_message_received:
                            self.on_message_received(packet)
                    
                    # Relais systématique
                    if packet.get("ttl", 0) > 0:
                        packet["ttl"] -= 1
                        self._relay_packet(packet, exclude_ip=ip)
                        
            except: break
        
        if ip in self.peers: del self.peers[ip]
        sock.close()

    def _relay_packet(self, packet, exclude_ip=None):
        data = json.dumps(packet).encode()
        for ip, sock in list(self.peers.items()):
            if ip != exclude_ip:
                try: sock.send(data)
                except: pass

    def send_pulse(self, dest_friend_code: str, content: str, msg_type: str = "text"):
        """Envoie un message chiffré ou une commande au mesh."""
        dest_hash = x_pulse_hash(dest_friend_code.encode()).hex() if dest_friend_code != "broadcast" else "broadcast"
        packet = {
            "id": x_pulse_hash(os.urandom(32)).hex(),
            "sender_code": self.friend_code,
            "dest_hash": dest_hash,
            "type": msg_type,
            "content": content,
            "timestamp": time.time(),
            "ttl": 8
        }
        self.messages_seen.add(packet["id"])
        self._relay_packet(packet)

    def connect_to_peer(self, ip, port=42424):
        if ip in self.peers: return True
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, port))
            self.known_peer_addresses.add((ip, port))
            threading.Thread(target=self._handle_peer, args=(sock, (ip, port)), daemon=True).start()
            return True
        except: return False

    def stop(self):
        self.running = False
        self.server_socket.close()

if __name__ == "__main__":
    pass
