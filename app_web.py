import cv2
import mediapipe as mp
import numpy as np
import os
from flask import Flask, render_template, Response, jsonify

app = Flask(__name__)

# --- Configurações MediaPipe ---
mp_maos = mp.solutions.hands
mp_rosto = mp.solutions.face_mesh
mp_desenho = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Inicializar Mãos
maos = mp_maos.Hands(
    static_image_mode=False, 
    max_num_hands=2, 
    model_complexity=0, 
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Inicializar Rosto (Face Mesh)
rosto = mp_rosto.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Estado Global
estado_atual = {
    "gesto": "Nenhum",
    "expressao": "Neutro",
    "imagem": "neutro.jpg"
}

cap = cv2.VideoCapture(0)

def contar_dedos(landmarks, lateralidade="Right", orientacao="Palma"):
    pontas_dedos = [8, 12, 16, 20]
    dedos_levantados = []

    # Polegar
    # A lógica do polegar inverte dependendo se é Palma ou Costas
    if lateralidade == "Right":
        if orientacao == "Palma":
            # Palma: Polegar à esquerda (x menor)
            if landmarks[4].x < landmarks[3].x: 
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)
        else: # Costas
            # Costas: Polegar à direita (x maior)
            if landmarks[4].x > landmarks[3].x: 
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)
    else: # Left
        if orientacao == "Palma":
            # Palma: Polegar à direita (x maior)
            if landmarks[4].x > landmarks[3].x:
                dedos_levantados.append(1)
            else:
                dedos_levantados.append(0)
        else: # Costas
            # Costas: Polegar à esquerda (x menor)
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

import time

def detectar_expressao(face_landmarks):
    # Pontos chave do rosto (MediaPipe Face Mesh)
    # Lábio superior: 13, Lábio inferior: 14
    # Canto esquerdo boca: 61, Canto direito boca: 291
    # Topo rosto: 10, Queixo: 152 (para normalização vertical)
    # Maçã do rosto esq: 234, Maçã do rosto dir: 454 (para normalização horizontal)
    
    p = face_landmarks.landmark
    
    # Altura do rosto (Vertical)
    altura_rosto = p[152].y - p[10].y
    
    # Largura do rosto (Horizontal)
    largura_rosto = p[454].x - p[234].x
    
    # 1. Abertura da boca (Surpresa) - Normalizado pela altura
    abertura_boca = (p[14].y - p[13].y) / altura_rosto
    
    # 2. Largura da boca (Sorriso) - Normalizado pela largura do rosto
    largura_boca = (p[291].x - p[61].x) / largura_rosto
    
    if abertura_boca > 0.15: 
        return "Surpresa", "surpresa.jpg"
    elif largura_boca > 0.40: # Ajustado: > 40% da largura do rosto
        return "Sorriso", "sorriso.jpg"
    
    return "Neutro", None

def gerar_frames():
    global cap, estado_atual
    
    while True:
        if cap is None or not cap.isOpened():
            print("Tentando abrir a camera...")
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            time.sleep(1) # Esperar câmera inicializar
            
        sucesso, frame = cap.read()
        if not sucesso:
            # Se falhar, envia um frame preto com aviso
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "CAMERA NAO ENCONTRADA", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Atualiza estado para erro
            estado_atual["gesto"] = "Erro na Camera"
            estado_atual["imagem"] = "neutro.jpg"
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(1) # Evita loop rápido demais
            continue

        # Espelhar frame
        frame = cv2.flip(frame, 1)
        
        # Reduzir para processamento
        frame_small = cv2.resize(frame, (320, 240))
        frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
        
        # Processar mãos e rosto
        resultados_maos = maos.process(frame_rgb)
        resultados_rosto = rosto.process(frame_rgb)
        
        gesto_detectado = "Nenhuma mao"
        expressao_detectada = "Neutro"
        imagem_nome = "neutro.jpg"
        
        gestos_lista = []
        maior_prioridade = -1
        gesto_principal = "Nenhuma mao"

        # --- Lógica de Mãos ---
        if resultados_maos.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(resultados_maos.multi_hand_landmarks):
                mp_desenho.draw_landmarks(frame, hand_landmarks, mp_maos.HAND_CONNECTIONS)
                
                # Obter lateralidade (Right/Left)
                lateralidade = "Right"
                if resultados_maos.multi_handedness:
                    # Proteção contra índice fora do alcance (embora raro)
                    if idx < len(resultados_maos.multi_handedness):
                        lateralidade = resultados_maos.multi_handedness[idx].classification[0].label

                # --- Detecção de Orientação (Palma vs Costas) ---
                # P0: Pulso, P5: Base Indicador, P17: Base Mindinho
                p0 = hand_landmarks.landmark[0]
                p5 = hand_landmarks.landmark[5]
                p17 = hand_landmarks.landmark[17]
                
                # Produto vetorial (Cross Product) 2D para determinar a direção
                # V1 = P5 - P0, V2 = P17 - P0
                val_cross = (p5.x - p0.x) * (p17.y - p0.y) - (p5.y - p0.y) * (p17.x - p0.x)
                
                orientacao = ""
                if lateralidade == "Right":
                    orientacao = "Palma" if val_cross > 0 else "Costas"
                else: # Left
                    orientacao = "Palma" if val_cross < 0 else "Costas"

                total_dedos, lista_dedos = contar_dedos(hand_landmarks.landmark, lateralidade, orientacao)

                # Distância OK (Normalizada pelo tamanho da mão aprox)
                escala_mao = ((hand_landmarks.landmark[0].y - hand_landmarks.landmark[9].y)**2 + (hand_landmarks.landmark[0].x - hand_landmarks.landmark[9].x)**2)**0.5
                
                x4, y4 = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
                x8, y8 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
                distancia_ok = ((x4 - x8)**2 + (y4 - y8)**2)**0.5
                
                # Lógica Like melhorada
                # Polegar para cima: ponta (4) acima da articulação IP (3)
                polegar_pra_cima = hand_landmarks.landmark[4].y < hand_landmarks.landmark[3].y
                
                indicador_fechado = hand_landmarks.landmark[8].y > hand_landmarks.landmark[6].y
                medio_fechado = hand_landmarks.landmark[12].y > hand_landmarks.landmark[10].y
                anelar_fechado = hand_landmarks.landmark[16].y > hand_landmarks.landmark[14].y
                minimo_fechado = hand_landmarks.landmark[20].y > hand_landmarks.landmark[18].y
                
                outros_dedos_fechados = indicador_fechado and medio_fechado and anelar_fechado and minimo_fechado

                gesto_temp = f"Dedos: {total_dedos}"
                img_temp = "neutro.jpg"
                prioridade = 0

                if distancia_ok < (0.15 * escala_mao) and lista_dedos[2] == 1 and lista_dedos[3] == 1: # OK mais robusto
                    gesto_temp = "OK"
                    img_temp = "ok.jpg"
                    prioridade = 5
                elif polegar_pra_cima and outros_dedos_fechados:
                    gesto_temp = "LIKE"
                    img_temp = "like.jpg"
                    prioridade = 4
                elif total_dedos == 5:
                    gesto_temp = "Mao Aberta"
                    img_temp = "sol.jpg"
                    prioridade = 2
                elif outros_dedos_fechados: # Punho Fechado (Se não for Like, mas dedos fechados)
                    gesto_temp = "Punho Fechado"
                    img_temp = "lua.jpg"
                    prioridade = 1
                elif total_dedos == 2 and lista_dedos[1] == 1 and lista_dedos[2] == 1:
                    gesto_temp = "Paz e Amor"
                    img_temp = "paz.jpg"
                    prioridade = 3
                
                gestos_lista.append(f"{lateralidade} ({orientacao}): {gesto_temp}")
                
                if prioridade > maior_prioridade:
                    maior_prioridade = prioridade
                    imagem_nome = img_temp
                    gesto_principal = gesto_temp

        if gestos_lista:
            gesto_detectado = " | ".join(gestos_lista)
        
        # --- Lógica de Rosto (Prioridade sobre Mãos se detectar expressão forte) ---
        if resultados_rosto.multi_face_landmarks:
            for face_landmarks in resultados_rosto.multi_face_landmarks:
                # Desenhar malha do rosto (opcional, pode poluir muito)
                # mp_desenho.draw_landmarks(frame, face_landmarks, mp_rosto.FACEMESH_TESSELATION, landmark_drawing_spec=None, connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
                
                exp, img_exp = detectar_expressao(face_landmarks)
                expressao_detectada = exp
                
                # Se detectar uma expressão forte E não tiver gesto de mão importante, mostra a expressão
                if img_exp and gesto_principal in ["Nenhuma mao", "Punho Fechado", "Mao Aberta"] and "Dedos" not in gesto_principal:
                     # Damos prioridade para Sorriso/Surpresa sobre gestos simples
                     imagem_nome = img_exp
                exp, img_exp = detectar_expressao(face_landmarks)
                expressao_detectada = exp
                
                # Se detectar uma expressão forte E não tiver gesto de mão importante, mostra a expressão
                if img_exp and gesto_detectado in ["Nenhuma mao", "Punho Fechado", "Mao Aberta"] and "Dedos" not in gesto_detectado:
                     # Damos prioridade para Sorriso/Surpresa sobre gestos simples
                     imagem_nome = img_exp

        # Atualizar estado global
        estado_atual["gesto"] = f"{gesto_detectado} | {expressao_detectada}"
        estado_atual["imagem"] = imagem_nome

        # Codificar frame para JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gerar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/current_status')
def current_status():
    return jsonify(estado_atual)

if __name__ == "__main__":
    # Host 0.0.0.0 permite acesso de outros dispositivos na rede
    # debug=False é IMPORTANTE no Windows para não abrir a câmera 2 vezes
    app.run(debug=False, host='0.0.0.0', port=5000)
