import json
import os
from emp_crypto import EMPCrypto, x_pulse_hash

class EMPStorage:
    """
    Gestionnaire de stockage local.
    Gère les contacts, les messages et les demandes d'amis.
    """
    
    def __init__(self, user_password: str, storage_path: str = "storage/"):
        self.storage_path = storage_path
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)
            
        self.crypto = EMPCrypto(user_password)
        self.local_data_file = os.path.join(storage_path, "local_data.dat")
        
        # Structure par défaut
        self.data = {
            "my_pseudo": "Utilisateur",
            "my_friend_code": EMPCrypto.generate_friend_code(),
            "friends": {}, # {friend_code: name}
            "pending_requests": {}, # {friend_code: timestamp}
            "sent_requests": set(), # {friend_code}
            "messages": [] # [{sender, dest, content, timestamp, type}]
        }
        
        self.load_local_data()

    def load_local_data(self):
        if os.path.exists(self.local_data_file):
            try:
                with open(self.local_data_file, "rb") as f:
                    encrypted_data = f.read()
                    decrypted_str = self.crypto.decrypt(encrypted_data)
                    loaded_data = json.loads(decrypted_str)
                    # Merge to ensure new keys exist
                    for k, v in loaded_data.items():
                        self.data[k] = v
            except: pass

    def save_local_data(self):
        try:
            # Convert sets to lists for JSON
            data_to_save = self.data.copy()
            if isinstance(data_to_save["sent_requests"], set):
                data_to_save["sent_requests"] = list(data_to_save["sent_requests"])
                
            json_str = json.dumps(data_to_save)
            encrypted_data = self.crypto.encrypt(json_str)
            with open(self.local_data_file, "wb") as f:
                f.write(encrypted_data)
        except Exception as e:
            print(f"Erreur sauvegarde: {e}")

    def add_pending_request(self, friend_code: str):
        if friend_code not in self.data["friends"]:
            self.data["pending_requests"][friend_code] = os.urandom(4).hex()
            self.save_local_data()

    def accept_friend(self, friend_code: str, name: str = None):
        if friend_code in self.data["pending_requests"]:
            del self.data["pending_requests"][friend_code]
        if not name: name = f"Ami {friend_code[:4]}"
        self.data["friends"][friend_code] = name
        self.save_local_data()

    def add_message(self, sender: str, dest: str, content: str, msg_type: str = "text"):
        msg = {
            "sender": sender,
            "dest": dest,
            "content": content,
            "timestamp": x_pulse_hash(os.urandom(8)).hex()[:8],
            "type": msg_type
        }
        self.data["messages"].append(msg)
        self.save_local_data()

    def get_messages_for(self, friend_code: str):
        return [m for m in self.data["messages"] if m["sender"] == friend_code or m["dest"] == friend_code]

if __name__ == "__main__":
    pass
