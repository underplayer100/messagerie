import os
import base64

def x_pulse_hash(data: bytes) -> bytes:
    """
    Algorithme de hachage 'X-Pulse Hash' (Inventé, sans hashlib).
    Produit un hash de 32 octets (256 bits).
    """
    h = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ]
    data += b'\x80'
    while (len(data) + 8) % 64 != 0:
        data += b'\x00'
    data += (len(data) * 8).to_bytes(8, 'big')

    for i in range(0, len(data), 64):
        block = data[i:i+64]
        words = [int.from_bytes(block[j:j+4], 'big') for j in range(0, 64, 4)]
        a, b, c, d, e, f, g, h_val = h
        for r in range(32):
            tmp1 = (a ^ (b << 13 | b >> 19)) + (c ^ 0x9e3779b9)
            tmp2 = (e ^ (f << 17 | f >> 15)) + (g ^ 0x517cc1b7)
            h_val = g; g = f; f = e; e = (d + tmp1) & 0xFFFFFFFF; d = c; c = b; b = a
            a = (tmp1 + tmp2 + words[r % 16]) & 0xFFFFFFFF
        h = [(h[i] + val) & 0xFFFFFFFF for i, val in enumerate([a, b, c, d, e, f, g, h_val])]
    return b''.join(v.to_bytes(4, 'big') for v in h)

class EMPCrypto:
    """
    Système de chiffrement 'Vortex Cipher' (Inventé, sans hashlib).
    """
    
    def __init__(self, key_str: str):
        self.key = x_pulse_hash(key_str.encode())
        
    def _vortex_step(self, block: bytes, round_key: bytes) -> bytes:
        res = bytearray(len(block))
        for i in range(len(block)):
            val = block[i]
            rk = round_key[i % len(round_key)]
            res[i] = ((val << 3 | val >> 5) ^ rk) & 0xFF
        return bytes(res)

    def _pad(self, data: bytes) -> bytes:
        pad_len = 32 - (len(data) % 32)
        return data + bytes([pad_len] * pad_len)

    def _unpad(self, data: bytes) -> bytes:
        pad_len = data[-1]
        if pad_len > 32: return data # Safety
        return data[:-pad_len]

    def encrypt(self, plaintext: str) -> str:
        """Chiffre et retourne une chaîne en Base64."""
        data = self._pad(plaintext.encode('utf-8'))
        encrypted = b""
        prev_block = self.key
        for i in range(0, len(data), 32):
            block = data[i:i+32]
            mixed_block = bytes(a ^ b for a, b in zip(block, prev_block))
            round_key = x_pulse_hash(prev_block + bytes([i // 32]))
            encrypted_block = self._vortex_step(mixed_block, round_key)
            encrypted += encrypted_block
            prev_block = encrypted_block
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt(self, b64_ciphertext: str) -> str:
        """Déchiffre depuis une chaîne Base64."""
        try:
            ciphertext = base64.b64decode(b64_ciphertext)
            decrypted = b""
            prev_block = self.key
            def rotate_right(v, n): return ((v >> n) | (v << (8 - n))) & 0xFF
            for i in range(0, len(ciphertext), 32):
                block = ciphertext[i:i+32]
                round_key = x_pulse_hash(prev_block + bytes([i // 32]))
                inv_block = bytearray(32)
                for j in range(32):
                    inv_block[j] = rotate_right(block[j] ^ round_key[j % 32], 3)
                plain_block = bytes(a ^ b for a, b in zip(inv_block, prev_block))
                decrypted += plain_block
                prev_block = block
            return self._unpad(decrypted).decode('utf-8')
        except: return "[Erreur Déchiffrement]"

    @staticmethod
    def derive_shared_key(code1: str, code2: str):
        """Dérive une clé partagée déterministe entre deux codes amis."""
        combined = "".join(sorted([code1, code2]))
        return x_pulse_hash(combined.encode()).hex()

    @staticmethod
    def generate_friend_code():
        raw = os.urandom(32)
        return x_pulse_hash(raw).hex()[:12].upper()

if __name__ == "__main__":
    pass
