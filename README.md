# 🖐️ Sistema de Reconhecimento de Gestos e Expressões Faciais (MVP)

Este projeto é um MVP (Minimum Viable Product) de uma aplicação web que utiliza Visão Computacional para detectar gestos das mãos e expressões faciais em tempo real através da webcam. O sistema interpreta os movimentos e exibe feedbacks visuais correspondentes na interface.

## 🚀 Funcionalidades

### 👐 Detecção de Mãos
O sistema é capaz de rastrear até **duas mãos** simultaneamente e identificar:
*   **Gestos:**
    *   ☀️ **Mão Aberta:** Exibe imagem de Sol.
    *   🌑 **Punho Fechado:** Exibe imagem de Lua.
    *   👌 **OK:** Gesto de OK.
    *   👍 **Like (Joinha):** Gesto de aprovação.
    *   ✌️ **Paz e Amor:** Gesto de V.
*   **Orientação:** Identifica se a mão está mostrando a **Palma** ou as **Costas**.
*   **Contagem de Dedos:** Contagem precisa independente da orientação da mão.

### 😀 Detecção de Expressões Faciais
Utilizando a malha facial (Face Mesh), o sistema detecta:
*   😄 **Sorriso:** Baseado na largura da boca.
*   😮 **Surpresa:** Baseado na abertura vertical da boca.

### 💻 Interface Web
*   Desenvolvida com **Flask** (Backend) e **Bootstrap 5** (Frontend).
*   Feed de vídeo em tempo real.
*   Painel de status dinâmico que mostra os gestos detectados por cada mão (Esquerda/Direita).
*   Atualização automática da imagem de resposta sem recarregar a página.

## 🛠️ Tecnologias Utilizadas

*   **Python 3.11**
*   **OpenCV:** Captura e processamento de imagem.
*   **MediaPipe:** Modelos de IA para detecção de mãos e face mesh.
*   **Flask:** Servidor web.
*   **NumPy:** Operações matemáticas.

## 📦 Instalação e Execução

1.  **Pré-requisitos:**
    *   Python 3.11 instalado (Recomendado devido a compatibilidade do MediaPipe).
    *   Webcam conectada.

2.  **Instale as dependências:**
    ```bash
    pip install opencv-python mediapipe flask numpy
    ```

3.  **Gere as imagens de feedback (Opcional):**
    Caso as imagens não existam na pasta `static/images`, execute:
    ```bash
    python gerar_novas_imagens.py
    ```

4.  **Execute a aplicação:**
    ```bash
    python app_web.py
    ```

5.  **Acesse no navegador:**
    Abra `http://127.0.0.1:5000` no seu navegador web.

## 📂 Estrutura do Projeto

*   `app_web.py`: Código principal da aplicação Flask e lógica de visão computacional.
*   `templates/index.html`: Interface do usuário (HTML/JS).
*   `static/images/`: Imagens geradas para feedback visual.
*   `gerar_novas_imagens.py`: Script utilitário para criar as imagens de resposta.

## 📝 Notas de Desenvolvimento

*   O sistema prioriza gestos de comando (OK, Like) sobre gestos neutros.
*   Expressões faciais fortes (Sorriso/Surpresa) têm prioridade de exibição se as mãos estiverem em posição neutra.
*   Foi implementada uma lógica de correção para contagem de dedos quando a mão está de costas para a câmera.
