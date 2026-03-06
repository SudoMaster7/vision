try:
    import cv2
except Exception:
    cv2 = None

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    import numpy as np
except Exception:
    np = None
import os
import datetime
try:
    import sounddevice as sd
except Exception:
    sd = None
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for

app = Flask(__name__)
CLOUD_MODE = os.getenv("VERCEL") == "1"
CV_AVAILABLE = cv2 is not None and mp is not None and np is not None

# --- Configurações MediaPipe ---
mp_maos = mp.solutions.hands if mp is not None else None
mp_rosto = mp.solutions.face_mesh if mp is not None else None
mp_desenho = mp.solutions.drawing_utils if mp is not None else None
mp_drawing_styles = mp.solutions.drawing_styles if mp is not None else None

def inicializar_mediapipe():
    if not CV_AVAILABLE or CLOUD_MODE:
        return None, None

    try:
        maos_local = mp_maos.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        rosto_local = mp_rosto.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        return maos_local, rosto_local
    except FileNotFoundError as erro:
        mensagem = (
            "\n[ERRO] Falha ao iniciar MediaPipe.\n"
            "No Windows, isso normalmente acontece quando o ambiente virtual está em caminho com acento (ex.: 'Área de Trabalho').\n"
            "Solução recomendada:\n"
            "1) Criar venv em caminho sem acentos, por exemplo: C:/venvs/visionsudo311\n"
            "2) Instalar dependências nele\n"
            "3) Rodar com: C:/venvs/visionsudo311/Scripts/python.exe app_web.py\n"
        )
        raise RuntimeError(mensagem) from erro


maos, rosto = inicializar_mediapipe()

# Estado Global
estado_atual = {
    "gesto": "Nenhum",
    "gesto_principal": "Nenhuma mao",
    "expressao": "Neutro",
    "imagem": "neutro.jpg"
}

config_dispositivos = {
    "camera_index": 0,
    "microfone_index": None
}

cap = None

def listar_cameras(max_tentativas=6):
    if cv2 is None or CLOUD_MODE:
        return []

    cameras = []
    for idx in range(max_tentativas):
        tentativa = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not tentativa.isOpened():
            tentativa = cv2.VideoCapture(idx)

        if tentativa.isOpened():
            cameras.append({"index": idx, "nome": f"Câmera {idx}"})
            tentativa.release()

    if not cameras:
        cameras.append({"index": 0, "nome": "Câmera 0 (padrão)"})

    return cameras

def _tentar_abrir_camera_por_indice(index):
    if cv2 is None or CLOUD_MODE:
        return None

    if index is None:
        return None

    tentativa = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not tentativa.isOpened():
        tentativa.release()
        tentativa = cv2.VideoCapture(index)

    if not tentativa.isOpened():
        tentativa.release()
        return None

    return tentativa

def listar_microfones():
    if sd is None or CLOUD_MODE:
        return []

    microfones = []
    try:
        dispositivos = sd.query_devices()
        for idx, dispositivo in enumerate(dispositivos):
            if dispositivo.get("max_input_channels", 0) > 0:
                microfones.append({"index": idx, "nome": dispositivo.get("name", f"Microfone {idx}")})
    except Exception:
        microfones = []

    return microfones

def abrir_camera(index, fallback=True):
    global cap

    if cv2 is None or CLOUD_MODE:
        return False

    camera_anterior = cap
    nova_cap = _tentar_abrir_camera_por_indice(index)
    indice_em_uso = index

    if nova_cap is None and fallback:
        for camera in listar_cameras():
            idx = camera["index"]
            nova_cap = _tentar_abrir_camera_por_indice(idx)
            if nova_cap is not None:
                indice_em_uso = idx
                break

    if nova_cap is None:
        return False

    cap = nova_cap
    config_dispositivos["camera_index"] = indice_em_uso

    if camera_anterior is not None and camera_anterior is not cap:
        camera_anterior.release()

    return True

def aplicar_microfone(index):
    microfones = listar_microfones()
    indices_validos = {item["index"] for item in microfones}

    if index is None:
        config_dispositivos["microfone_index"] = None
        return True

    if index in indices_validos:
        config_dispositivos["microfone_index"] = index
        return True

    return False

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
    
    ultimo_print = 0
    COOLDOWN_PRINT = 3.0 # 3 segundos de intervalo entre prints

    while True:
        if cap is None or not cap.isOpened():
            print("Tentando abrir a camera...")
            if not abrir_camera(config_dispositivos["camera_index"], fallback=True):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "CAMERA NAO ENCONTRADA", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                estado_atual["gesto"] = "Erro na Camera"
                estado_atual["imagem"] = "neutro.jpg"

                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                time.sleep(1)
                continue

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

                    # Funcionalidade: Print ao fazer OK com as Costas da Mão Direita
                    if lateralidade == "Right" and orientacao == "Costas":
                        agora = time.time() + 0.3 # pequeno ajuste de tempo
                        if agora - ultimo_print > COOLDOWN_PRINT:
                            if not os.path.exists("screenshots"):
                                os.makedirs("screenshots")
                            
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"screenshots/print_{timestamp}.jpg"
                            # Salvar o frame original (sem desenhos do mediapipe se possível, mas aqui 'frame' já tem desenhos)
                            # Se quisesse limpo, teria que ter salvo uma cópia antes do mp_desenho.draw_landmarks
                            # Mas o usuário pediu "print da camera", então com os desenhos é aceitável/esperado para debug visual.
                            cv2.imwrite(filename, frame)
                            print(f"📸 Screenshot salvo: {filename}")
                            ultimo_print = agora
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
                exp, img_exp = detectar_expressao(face_landmarks)
                expressao_detectada = exp

                # Prioriza expressão facial quando não há gesto de mão forte
                if img_exp and gesto_principal in ["Nenhuma mao", "Punho Fechado", "Mao Aberta"] and "Dedos" not in gesto_principal:
                    imagem_nome = img_exp

        # Atualizar estado global
        estado_atual["gesto"] = gesto_detectado
        estado_atual["gesto_principal"] = gesto_principal
        estado_atual["expressao"] = expressao_detectada
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
    if CLOUD_MODE or not CV_AVAILABLE:
        return redirect(url_for('static', filename='images/neutro.jpg'))
    return Response(gerar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- Lógica de Pintura Virtual ---
canvas_pintura = np.zeros((480, 640, 3), dtype=np.uint8) if np is not None else None
cor_pincel = (255, 0, 0) # Azul BGR (OpenCV usa BGR)
ponto_anterior = (0, 0)

def gerar_frames_pintura():
    global cap, canvas_pintura, cor_pincel, ponto_anterior
    
    # Cores disponíveis (BGR)
    cores = [
        ((255, 0, 0), "Azul"),    # Azul
        ((0, 255, 0), "Verde"),   # Verde
        ((0, 0, 255), "Vermelho"),# Vermelho
        ((0, 0, 0), "Borracha")   # Preto (Apagar)
    ]
    
    # Áreas dos botões de cor (x, y, w, h)
    botoes = []
    largura_botao = 100
    for i in range(len(cores)):
        botoes.append( (40 + i * 120, 20, largura_botao, 60) )

    while True:
        if cap is None or not cap.isOpened():
            if not abrir_camera(config_dispositivos["camera_index"], fallback=True):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "ERRO NA CAMERA", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.5)
                continue

            time.sleep(1)
            
        sucesso, frame = cap.read()
        if not sucesso:
            # Frame de erro para não travar o vídeo
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "ERRO NA CAMERA", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.5)
            continue

        frame = cv2.flip(frame, 1)
        # Forçar tamanho 640x480 para bater com o canvas
        frame = cv2.resize(frame, (640, 480))
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultados = maos.process(frame_rgb)
        
        # Desenhar interface (botões)
        for i, (cor, nome) in enumerate(cores):
            x, y, w, h = botoes[i]
            cv2.rectangle(frame, (x, y), (x+w, y+h), cor, -1)
            cv2.putText(frame, nome, (x+10, y+40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            # Borda branca no botão selecionado
            if cor == cor_pincel:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 3)

        if resultados.multi_hand_landmarks:
            for hand_landmarks in resultados.multi_hand_landmarks:
                # Pontos importantes
                # 8: Ponta do indicador
                # 12: Ponta do médio (para verificar se está levantado ou não)
                
                x8, y8 = int(hand_landmarks.landmark[8].x * 640), int(hand_landmarks.landmark[8].y * 480)
                
                # Verificar se indicador está levantado (y da ponta < y da articulação média)
                indicador_levantado = hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y
                
                # Verificar se é mão aberta (para limpar tela)
                # Contagem rápida de dedos levantados
                dedos_up = 0
                if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y: dedos_up += 1
                if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y: dedos_up += 1
                if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y: dedos_up += 1
                if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y: dedos_up += 1
                
                if dedos_up >= 4: # Mão aberta -> Limpar
                    canvas_pintura = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "TELA LIMPA", (250, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    ponto_anterior = (0, 0)
                
                elif indicador_levantado:
                    # Desenhar círculo na ponta do dedo com a cor atual
                    cv2.circle(frame, (x8, y8), 10, cor_pincel, -1)
                    
                    # Verificar colisão com botões (Seleção de Cor)
                    if y8 < 100: # Se estiver no topo da tela
                        for i, (x, y, w, h) in enumerate(botoes):
                            if x < x8 < x+w and y < y8 < y+h:
                                cor_pincel = cores[i][0]
                                ponto_anterior = (0, 0) # Resetar traço para não riscar ao selecionar
                    
                    # Desenhar no canvas
                    else:
                        if ponto_anterior == (0, 0):
                            ponto_anterior = (x8, y8)
                        
                        # Desenhar linha
                        cv2.line(canvas_pintura, ponto_anterior, (x8, y8), cor_pincel, 5)
                        ponto_anterior = (x8, y8)
                else:
                    ponto_anterior = (0, 0)

        # Mesclar canvas com frame
        # Criar máscara onde há desenho
        img_gray = cv2.cvtColor(canvas_pintura, cv2.COLOR_BGR2GRAY)
        _, img_inv = cv2.threshold(img_gray, 10, 255, cv2.THRESH_BINARY_INV)
        img_inv = cv2.cvtColor(img_inv, cv2.COLOR_GRAY2BGR)
        
        # Onde tem desenho no canvas, usamos o canvas. Onde não tem, usamos o frame.
        frame = cv2.bitwise_and(frame, img_inv)
        frame = cv2.bitwise_or(frame, canvas_pintura)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/pintura')
def pintura():
    return render_template('pintura.html')

@app.route('/video_feed_pintura')
def video_feed_pintura():
    if CLOUD_MODE or not CV_AVAILABLE:
        return redirect(url_for('static', filename='images/neutro.jpg'))
    return Response(gerar_frames_pintura(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/current_status')
def current_status():
    return jsonify(estado_atual)

@app.route('/devices')
def devices():
    return jsonify({
        "cameras": listar_cameras(),
        "microfones": listar_microfones(),
        "cloud_mode": CLOUD_MODE,
        "selecionado": {
            "camera_index": config_dispositivos["camera_index"],
            "microfone_index": config_dispositivos["microfone_index"]
        }
    })

@app.route('/set_devices', methods=['POST'])
def set_devices():
    if CLOUD_MODE:
        return jsonify({"ok": False, "mensagem": "Seleção de dispositivos não disponível no deploy cloud."}), 400

    dados = request.get_json(silent=True) or {}
    camera_index = dados.get("camera_index", config_dispositivos["camera_index"])
    microfone_index = dados.get("microfone_index", config_dispositivos["microfone_index"])

    try:
        if camera_index is not None:
            camera_index = int(camera_index)
        if microfone_index is not None:
            microfone_index = int(microfone_index)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "mensagem": "Índices inválidos."}), 400

    if camera_index is None:
        camera_index = config_dispositivos["camera_index"]

    if not abrir_camera(camera_index, fallback=False):
        return jsonify({"ok": False, "mensagem": f"Não foi possível abrir a câmera {camera_index}."}), 400

    if not aplicar_microfone(microfone_index):
        return jsonify({"ok": False, "mensagem": "Microfone selecionado é inválido."}), 400

    return jsonify({
        "ok": True,
        "mensagem": "Dispositivos atualizados com sucesso.",
        "selecionado": {
            "camera_index": config_dispositivos["camera_index"],
            "microfone_index": config_dispositivos["microfone_index"]
        }
    })

if __name__ == "__main__":
    # Host 0.0.0.0 permite acesso de outros dispositivos na rede
    # debug=False é IMPORTANTE no Windows para não abrir a câmera 2 vezes
    app.run(debug=False, host='0.0.0.0', port=5000)
