"""Sistema de Planificación de Rutas Turísticas de Manabí. Punto de entrada."""
import tkinter as tk
from tkinter import messagebox

from datos import CARPETA_DATOS, preparar_datos_iniciales
from interfaz import App

if __name__ == "__main__":
    try:
        preparar_datos_iniciales()
        app = App()
    except Exception as error:
        # El ejecutable no tiene consola: sin esto un archivo JSON dañado cerraría el programa sin aviso
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Rutas turísticas de Manabí",
                             f"No se pudo iniciar el programa.\n\n{error}\n\nCarpeta de datos:\n{CARPETA_DATOS}")
        raise SystemExit(1)
    app.mainloop()
