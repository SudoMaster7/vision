import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import PIL.Image, PIL. ImageTk
import mediapipe as mp
import numpy as np
import os

class AppGestos:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.geometry("1300x700")

        # --- Configurações MediaPipe Otimizadas ---
        self.mp_maos = mp.solutions.hands
        self.mp_desenho = mp.solutions.drawing_utils
        # model_complexity=0 usa o modelo "Lite", muito mais rápido para CPU
        self.maos = self.mp_maos.Hands(
            static_image_mode=False, 
            max_num_hands=1, 
            model_complexity=0, 
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # --- Carregar Imagens de Resposta ---
        self.carregar_imagens_resposta()

        # --- Layout ---
        # Frame Superior (Controles)
        self.frame_controles = tk.Frame(window)
        self.frame_controles.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.btn_webcam = tk.Button(self.frame_controles, text="Usar Webcam (Padrão)", command=lambda: self.iniciar_camera(0))
        self.btn_webcam.pack(side=tk.LEFT, padx=5)

        self.btn_webcam2 = tk.Button(self.frame_controles, text="Usar Webcam (Externa/Outra)", command=lambda: self.iniciar_camera(1))
        self.btn_webcam2.pack(side=tk.LEFT, padx=5)

        self.btn_arquivo = tk.Button(self.frame_controles, text="Carregar Arquivo de Vídeo", command=self.carregar_video)
        self.btn_arquivo.pack(side=tk.LEFT, padx=5)

        self.lbl_status = tk.Label(self.frame_controles, text="Status: Aguardando seleção de fonte...", fg="blue")
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        # Frame Central (Vídeos)
        self.frame_videos = tk.Frame(window)
        self.frame_videos.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

        # Canvas para o Vídeo da Câmera
        self.canvas_video = tk.Canvas(self.frame_videos, width=640, height=480, bg="black")
        self.canvas_video.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Canvas para a Imagem de Resposta (Sol/Lua)
        self.canvas_resposta = tk.Canvas(self.frame_videos, width=640, height=480, bg="gray")
        self.canvas_resposta.pack(side=tk.LEFT, padx=10, pady=10)

        # Variáveis de Controle
        self.cap = None
        self.delay = 15 # ms
        self.rodando = False

        self.window.protocol("WM_DELETE_WINDOW", self.fechar_app)
        self.window.mainloop()

    def carregar_imagens_resposta(self):
        caminho_imagens = "imagens"
        if not os.path.exists(caminho_imagens):
            os.makedirs(caminho_imagens)
            # Se não existirem, cria imagens simples (preto/branco) para não quebrar
            self.img_sol = np.zeros((480, 640, 3), dtype=np.uint8)
            self.img_sol[:] = (0, 255, 255) # Amarelo
            self.img_lua = np.zeros((480, 640, 3), dtype=np.uint8)
            self.img_lua[:] = (50, 50, 50) # Cinza
            self.img_neutro = np.zeros((480, 640, 3), dtype=np.uint8)

        else:
            self.img_sol = cv2.imread(os.path.join(caminho_imagens, "sol.jpg"))
            self.img_lua = cv2.imread(os.path.join(caminho_imagens, "lua.jpg"))
            self.img_neutro = cv2.imread(os.path.join(caminho_imagens, "neutro.jpg"))
            self.img_ok = cv2.imread(os.path.join(caminho_imagens, "ok.jpg"))
            self.img_like = cv2.imread(os.path.join(caminho_imagens, "like.jpg"))
            self.img_paz = cv2.imread(os.path.join(caminho_imagens, "paz.jpg"))
            
            # Fallback se falhar o load
            if self.img_sol is None: self.img_sol = np.zeros((480, 640, 3), dtype=np.uint8)
            if self.img_lua is None: self.img_lua = np.zeros((480, 640, 3), dtype=np.uint8)
            if self.img_neutro is None: self.img_neutro = np.zeros((480, 640, 3), dtype=np.uint8)
            if self.img_ok is None: self.img_ok = np.zeros((480, 640, 3), dtype=np.uint8)
            if self.img_like is None: self.img_like = np.zeros((480, 640, 3), dtype=np.uint8)
            if self.img_paz is None: self.img_paz = np.zeros((480, 640, 3), dtype=np.uint8)

        # Converter para RGB para exibir no Tkinter
        self.img_sol = cv2.cvtColor(self.img_sol, cv2.COLOR_BGR2RGB)
        self.img_lua = cv2.cvtColor(self.img_lua, cv2.COLOR_BGR2RGB)
        self.img_neutro = cv2.cvtColor(self.img_neutro, cv2.COLOR_BGR2RGB)
        self.img_ok = cv2.cvtColor(self.img_ok, cv2.COLOR_BGR2RGB)
        self.img_like = cv2.cvtColor(self.img_like, cv2.COLOR_BGR2RGB)
        self.img_paz = cv2.cvtColor(self.img_paz, cv2.COLOR_BGR2RGB)

    def iniciar_camera(self, index=0):
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            messagebox.showerror("Erro", f"Não foi possível abrir a câmera {index}.")
            self.lbl_status.config(text="Erro ao abrir câmera.", fg="red")
            return

        self.rodando = True
        self.lbl_status.config(text=f"Usando Câmera {index}", fg="green")
        self.atualizar_frame()

    def carregar_video(self):
        arquivo = filedialog.askopenfilename(title="Selecione um vídeo", filetypes=[("Arquivos de Vídeo", "*.mp4 *.avi *.mov")])
        if arquivo:
            if self.cap is not None:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(arquivo)
            if not self.cap.isOpened():
                messagebox.showerror("Erro", "Não foi possível abrir o arquivo de vídeo.")
                return
            
            self.rodando = True
            self.lbl_status.config(text=f"Reproduzindo: {os.path.basename(arquivo)}", fg="green")
            self.atualizar_frame()

    def contar_dedos(self, landmarks):
        pontas_dedos = [8, 12, 16, 20]
        dedos_levantados = []

        # Polegar
        if landmarks[4].x < landmarks[3].x: 
            dedos_levantados.append(1)
        else:
            dedos_levantados.append(0)

        # Outros dedos
        for ponta in pontas_dedos:
            if landmarks[ponta].y < landmarks[ponta - 2].y:
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)

        return sum(dedos_levantados), dedos_levantados

    def atualizar_frame(self):
        if self.rodando and self.cap.isOpened():
            ret, frame = self.cap.read()
            
            if not ret:
                # Se for vídeo e acabar, reinicia
                self.rodando = False
                return
            
            # Reduzir resolução para processamento (aumenta muito o FPS)
            frame_small = cv2.resize(frame, (320, 240))
            frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            gesto_texto = "Nenhuma mao"
            imagem_resposta_atual = self.img_neutro
            resultados = self.maos.process(frame_rgb)

            if resultados.multi_hand_landmarks:
                for hand_landmarks in resultados.multi_hand_landmarks:
                    self.mp_desenho.draw_landmarks(frame, hand_landmarks, self.mp_maos.HAND_CONNECTIONS)
                    
                    total_dedos, lista_dedos = self.contar_dedos(hand_landmarks.landmark)

                    # --- Lógica Avançada de Gestos ---
                    
                    # 1. Detectar OK (Ponta do Polegar perto da Ponta do Indicador)
                    # Distância Euclidiana simples entre ponto 4 e 8
                    x4, y4 = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
                    x8, y8 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
                    distancia_ok = ((x4 - x8)**2 + (y4 - y8)**2)**0.5
                    
                    # 2. Detectar Like (Polegar para cima, outros dedos fechados)
                    # Polegar (4) acima da base do indicador (5) e dedos fechados
                    # Nota: Y cresce para baixo, então "acima" é valor menor
                    polegar_pra_cima = hand_landmarks.landmark[4].y < hand_landmarks.landmark[7].y
                    outros_dedos_fechados = lista_dedos[1] == 0 and lista_dedos[2] == 0 and lista_dedos[3] == 0

                    if distancia_ok < 0.05 and lista_dedos[2] == 1 and lista_dedos[3] == 1:
                        gesto_texto = "OK"
                        imagem_resposta_atual = self.img_ok
                    elif polegar_pra_cima and outros_dedos_fechados:
                        gesto_texto = "LIKE (Joinha)"
                        imagem_resposta_atual = self.img_like
                    elif total_dedos == 5:
                        gesto_texto = "Mao Aberta"
                        imagem_resposta_atual = self.img_sol
                    elif total_dedos == 0:
                        gesto_texto = "Punho Fechado"
                        imagem_resposta_atual = self.img_lua
                    elif total_dedos == 2 and lista_dedos[1] == 1 and lista_dedos[2] == 1:
                        gesto_texto = "Paz e Amor"
                        imagem_resposta_atual = self.img_paz
                    else:
                        gesto_texto = f"Dedos: {total_dedos}"

                    cv2.putText(frame, f"Gesto: {gesto_texto}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Atualizar Canvas Vídeo
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (640, 480))
            self.photo_video = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
            self.canvas_video.create_image(0, 0, image=self.photo_video, anchor=tk.NW)

            # Atualizar Canvas Resposta
            imagem_resposta_atual = cv2.resize(imagem_resposta_atual, (640, 480))
            self.photo_resposta = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(imagem_resposta_atual))
            self.canvas_resposta.create_image(0, 0, image=self.photo_resposta, anchor=tk.NW)

            self.window.after(self.delay, self.atualizar_frame)

    def fechar_app(self):
        if self.cap:
            self.cap.release()
        self.window.destroy()

if __name__ == "__main__":
    AppGestos(tk.Tk(), "Controle por Gestos - Interface Gráfica")
