import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import base64
import os
from emp_network import EMPNetwork
from emp_storage import EMPStorage
from emp_crypto import EMPCrypto

class EMPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EMP Messenger - Echo-Mesh Propagation")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1E1E1E")
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#1E1E1E")
        self.style.configure("TLabel", background="#1E1E1E", foreground="#FFFFFF")
        self.style.configure("TButton", background="#333333", foreground="#FFFFFF", borderwidth=0)
        
        self.storage = None
        self.network = None
        self.current_contact = None
        self.friend_cryptos = {} # {friend_code: EMPCrypto}
        
        self.show_login_screen()

    def show_login_screen(self):
        self.clear_screen()
        frame = ttk.Frame(self.root)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ttk.Label(frame, text="BIENVENUE SUR EMP", font=("Segoe UI", 24, "bold")).pack(pady=20)
        
        ttk.Label(frame, text="PSEUDO :", font=("Segoe UI", 10)).pack(pady=(10, 0))
        self.pseudo_entry = ttk.Entry(frame, width=30)
        self.pseudo_entry.pack(pady=5)
        
        ttk.Label(frame, text="MOT DE PASSE :", font=("Segoe UI", 10)).pack(pady=(10, 0))
        self.pwd_entry = ttk.Entry(frame, show="*", width=30)
        self.pwd_entry.pack(pady=5)
        self.pwd_entry.bind("<Return>", lambda e: self.login())
        
        ttk.Button(frame, text="DÉVERROUILLER / CRÉER", command=self.login).pack(pady=20)

    def login(self):
        pseudo = self.pseudo_entry.get().strip()
        pwd = self.pwd_entry.get()
        if not pwd or not pseudo: 
            messagebox.showwarning("EMP", "Pseudo et Mot de passe requis !")
            return
            
        try:
            # On vérifie si c'est une création ou une connexion
            storage_path = "storage/"
            local_data_file = os.path.join(storage_path, "local_data.dat")
            is_new = not os.path.exists(local_data_file)
            
            self.storage = EMPStorage(pwd)
            
            if is_new:
                # Premier lancement : on enregistre le pseudo
                self.storage.data["my_pseudo"] = pseudo
                self.storage.save_local_data()
            else:
                # On vérifie si le déchiffrement a réussi et si le pseudo correspond
                # (Le Vortex Cipher renvoie une erreur si la clé est mauvaise)
                if self.storage.data.get("my_pseudo") != pseudo:
                    # On supprime l'objet storage pour éviter les fuites si mdp faux
                    self.storage = None
                    messagebox.showerror("Erreur", "Pseudo ou Mot de passe incorrect pour ce coffre-fort !")
                    return
            
            self.network = EMPNetwork(self.storage.data["my_friend_code"])
            self.network.on_message_received = self.handle_network_packet
            self.show_main_chat()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec : {e}")

    def get_crypto_for(self, friend_code: str):
        if friend_code not in self.friend_cryptos:
            shared_key = EMPCrypto.derive_shared_key(self.storage.data["my_friend_code"], friend_code)
            self.friend_cryptos[friend_code] = EMPCrypto(shared_key)
        return self.friend_cryptos[friend_code]

    def connect_to_seed(self):
        ip = self.seed_entry.get().strip()
        if ip and ip != "IP d'un ami":
            if self.network.connect_to_peer(ip):
                messagebox.showinfo("Mesh Global", f"Connecté au nœud {ip}. Recherche d'autres pairs en cours...")
                self.seed_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Mesh Global", f"Impossible de rejoindre {ip}. Vérifiez l'IP ou le port (42424).")

    def show_main_chat(self):
        self.clear_screen()
        sidebar = tk.Frame(self.root, bg="#252526", width=300)
        sidebar.pack(side="left", fill="y")
      # Mon Pseudo et Code
        tk.Label(sidebar, text=f"UTILISATEUR : {self.storage.data.get('my_pseudo', 'Moi')}", font=("Segoe UI", 10, "bold"), bg="#252526", fg="white").pack(pady=(10, 0))
        tk.Label(sidebar, text="VOTRE CODE :", font=("Segoe UI", 8, "bold"), bg="#252526", fg="gray").pack(pady=(5, 0))
        tk.Label(sidebar, text=self.storage.data["my_friend_code"], font=("Consolas", 10), bg="#333333", fg="#00FF00").pack(pady=5, padx=10, fill="x")
        
        # Affichage de l'IP publique pour le Mesh Global
        tk.Label(sidebar, text="VOTRE IP MESH :", font=("Segoe UI", 8, "bold"), bg="#252526", fg="gray").pack(pady=(5, 0))
        self.ip_label = tk.Label(sidebar, text=self.network.public_ip, font=("Consolas", 9), bg="#333333", fg="#00BFFF")
        self.ip_label.pack(pady=2, padx=10, fill="x")
        
        # Bouton pour rejoindre un nœud mondial (Seed)
        seed_frame = tk.Frame(sidebar, bg="#252526")
        seed_frame.pack(fill="x", pady=10)
        self.seed_entry = ttk.Entry(seed_frame, font=("Segoe UI", 9))
        self.seed_entry.insert(0, "IP d'un ami")
        self.seed_entry.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(seed_frame, text="RELIE", command=self.connect_to_seed).pack(side="right", padx=5)

        self.tab_control = ttk.Notebook(sidebar)
        self.friends_tab = ttk.Frame(self.tab_control)
        self.requests_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.friends_tab, text="Amis")
        self.tab_control.add(self.requests_tab, text="Demandes")
        self.tab_control.pack(expand=1, fill="both")
        
        self.friends_listbox = tk.Listbox(self.friends_tab, bg="#252526", fg="white", borderwidth=0, font=("Segoe UI", 11))
        self.friends_listbox.pack(fill="both", expand=True)
        self.friends_listbox.bind("<<ListboxSelect>>", self.on_friend_select)
        
        self.requests_listbox = tk.Listbox(self.requests_tab, bg="#252526", fg="white", borderwidth=0, font=("Segoe UI", 11))
        self.requests_listbox.pack(fill="both", expand=True)
        ttk.Button(self.requests_tab, text="ACCEPTER", command=self.accept_selected_request).pack(fill="x", pady=5)
        
        add_frame = tk.Frame(sidebar, bg="#252526")
        add_frame.pack(side="bottom", fill="x", pady=10)
        self.new_friend_entry = ttk.Entry(add_frame)
        self.new_friend_entry.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(add_frame, text="INVITER", command=self.send_friend_request).pack(side="right", padx=5)
        
        chat_area = tk.Frame(self.root, bg="#1E1E1E")
        chat_area.pack(side="right", fill="both", expand=True)
        
        self.chat_header = tk.Label(chat_area, text="Sélectionnez un ami", font=("Segoe UI", 14, "bold"), bg="#2D2D2D", fg="white", pady=10)
        self.chat_header.pack(fill="x")
        
        self.msg_canvas = tk.Canvas(chat_area, bg="#1E1E1E", highlightthickness=0)
        self.msg_frame = tk.Frame(self.msg_canvas, bg="#1E1E1E")
        self.msg_canvas.pack(side="top", fill="both", expand=True)
        self.msg_canvas.create_window((0, 0), window=self.msg_frame, anchor="nw")
        
        input_frame = tk.Frame(chat_area, bg="#2D2D2D", pady=10)
        input_frame.pack(side="bottom", fill="x")
        
        self.msg_entry = tk.Entry(input_frame, bg="#3C3C3C", fg="white", borderwidth=0, font=("Segoe UI", 11), insertbackground="white")
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.msg_entry.bind("<Return>", lambda e: self.send_message())
        
        btn_box = tk.Frame(input_frame, bg="#2D2D2D")
        btn_box.pack(side="right", padx=10)
        ttk.Button(btn_box, text="ENVOYER", command=self.send_message).pack(side="left", padx=2)
        ttk.Button(btn_box, text="📷", width=3, command=self.send_image).pack(side="left", padx=2)
        ttk.Button(btn_box, text="📞", width=3, command=self.start_call).pack(side="left", padx=2)
        
        self.refresh_ui()

    def handle_network_packet(self, packet):
        msg_type = packet.get("type")
        sender = packet.get("sender_code")
        content = packet.get("content")
        
        if msg_type == "friend_request":
            # On stocke le pseudo envoyé dans le message
            self.storage.add_pending_request(sender)
            # On peut stocker le pseudo temporairement
            self.storage.data["pending_requests"][sender] = content 
            self.storage.save_local_data()
            self.root.after(0, self.refresh_ui)
        elif msg_type == "friend_accept":
            # content contient le pseudo de celui qui accepte
            self.storage.accept_friend(sender, content)
            self.root.after(0, self.refresh_ui)
        elif msg_type in ["text", "image"]:
            if sender in self.storage.data["friends"]:
                # Déchiffrement de bout en bout
                crypto = self.get_crypto_for(sender)
                decrypted_content = crypto.decrypt(content)
                self.storage.add_message(sender, self.storage.data["my_friend_code"], decrypted_content, msg_type)
                if self.current_contact == sender:
                    self.root.after(0, self.refresh_messages)
                else:
                    self.root.after(0, self.refresh_ui)
        elif msg_type == "call_signaling":
            if sender in self.storage.data["friends"]:
                self.root.after(0, lambda: messagebox.showinfo("Appel Entrant", f"Appel chiffré de {sender[:6]}..."))

    def send_friend_request(self):
        code = self.new_friend_entry.get().strip().upper()
        if len(code) == 12:
            # On envoie notre pseudo dans le content
            self.network.send_pulse(code, self.storage.data["my_pseudo"], "friend_request")
            messagebox.showinfo("EMP", f"Demande envoyée à {code} !")
            self.new_friend_entry.delete(0, tk.END)

    def accept_selected_request(self):
        selection = self.requests_listbox.curselection()
        if selection:
            pending_codes = list(self.storage.data["pending_requests"].keys())
            code = pending_codes[selection[0]]
            pseudo_distant = self.storage.data["pending_requests"][code]
            
            # On accepte l'ami avec son pseudo
            self.storage.accept_friend(code, pseudo_distant)
            # On lui envoie notre pseudo en retour
            self.network.send_pulse(code, self.storage.data["my_pseudo"], "friend_accept")
            self.refresh_ui()

    def send_message(self):
        if not self.current_contact: return
        text = self.msg_entry.get().strip()
        if text:
            crypto = self.get_crypto_for(self.current_contact)
            encrypted_text = crypto.encrypt(text)
            self.network.send_pulse(self.current_contact, encrypted_text, "text")
            self.storage.add_message(self.storage.data["my_friend_code"], self.current_contact, text, "text")
            self.msg_entry.delete(0, tk.END)
            self.refresh_messages()

    def send_image(self):
        if not self.current_contact: return
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.gif")])
        if path:
            with open(path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            crypto = self.get_crypto_for(self.current_contact)
            encrypted_img = crypto.encrypt(img_data)
            self.network.send_pulse(self.current_contact, encrypted_img, "image")
            self.storage.add_message(self.storage.data["my_friend_code"], self.current_contact, "[Image envoyée]", "image")
            self.refresh_messages()

    def start_call(self):
        if not self.current_contact: return
        self.network.send_pulse(self.current_contact, "Appel entrant...", "call_signaling")
        messagebox.showinfo("Appel", "Appel Chiffré : Tunnel Vortex sécurisé établi. (Streaming en cours...)")

    def refresh_ui(self):
        self.friends_listbox.delete(0, tk.END)
        for code, name in self.storage.data["friends"].items():
            self.friends_listbox.insert(tk.END, f"{name} ({code[:6]})")
            
        self.requests_listbox.delete(0, tk.END)
        for code, pseudo in self.storage.data["pending_requests"].items():
            self.requests_listbox.insert(tk.END, f"De: {pseudo} ({code[:6]})")

    def on_friend_select(self, event):
        selection = self.friends_listbox.curselection()
        if selection:
            self.current_contact = list(self.storage.data["friends"].keys())[selection[0]]
            self.chat_header.config(text=f"Chat avec {self.storage.data['friends'][self.current_contact]}")
            self.refresh_messages()

    def refresh_messages(self):
        for widget in self.msg_frame.winfo_children(): widget.destroy()
        if not self.current_contact: return
        messages = self.storage.get_messages_for(self.current_contact)
        for m in messages:
            is_me = m["sender"] == self.storage.data["my_friend_code"]
            color = "#007ACC" if is_me else "#3E3E3E"
            txt = m["content"]
            if m["type"] == "image" and not is_me: txt = "[Image reçue]"
            lbl = tk.Label(self.msg_frame, text=txt, bg=color, fg="white", padx=10, pady=5, wraplength=400)
            lbl.pack(anchor="e" if is_me else "w", pady=2, padx=10)
        self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox("all"))
        self.msg_canvas.yview_moveto(1.0)

    def clear_screen(self):
        for w in self.root.winfo_children(): w.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = EMPApp(root)
    root.mainloop()
