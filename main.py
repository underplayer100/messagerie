import tkinter as tk
from emp_gui import EMPApp
import sys

def main():
    """Point d'entrée principal de l'application EMP Messenger."""
    try:
        root = tk.Tk()
        app = EMPApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\nArrêt de l'application...")
        sys.exit(0)
    except Exception as e:
        print(f"Erreur fatale : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
