from flask import Flask, request, jsonify
import requests
import openai
import json
import os
import re
import time

app = Flask(__name__)

api_key = os.getenv('OPENAI_API_KEY')
#fiz uma mudança aqui
# Initialize the OpenAI client with the API key
client = openai.OpenAI(api_key=api_key)

messages_history = [] 
def split_text_preserving_sentences(text, max_chunk_size):
    # Define a expressão regular para encontrar os delimitadores de frase
    sentence_endings = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
    
    # Inicializa a lista para armazenar as partes
    parts = []
    
    # Divide o texto usando a expressão regular
    sentences = sentence_endings.split(text)
    
    current_chunk = ""
    
    for sentence in sentences:
        # Adiciona a sentença ao chunk atual
        if len(current_chunk) + len(sentence) + 1 > max_chunk_size:
            # Se adicionar a sentença exceder o tamanho máximo, salva o chunk atual e inicia um novo
            if current_chunk:
                parts.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += (sentence + " ")
    
    # Adiciona o último chunk
    if current_chunk:
        parts.append(current_chunk.strip())
    
    return parts

def send_message_in_parts(sender_phone, message, max_chunk_size=200, delay=0):
    # Divide o texto em partes sem quebrar frases
    parts = split_text_preserving_sentences(message, max_chunk_size)
    
    # Envia cada parte com um delay entre elas
    for part in parts:
        handle_whatsapp_message(sender_phone, part)
        time.sleep(delay)

def process_response(sender_phone, response_text, max_chunk_size=200, delay=1):
    send_message_in_parts(sender_phone, response_text, max_chunk_size, delay)
    
@app.route('/')
def index():
    return 'Hello, World!'

@app.route('/webhook', methods=['POST'])
def webhook():
    
    global messages_history
  
    data = request.json
    sender_phone = data.get('phone')
    arquivo_nome = sender_phone+"_dicionario.txt" #CARREGA O HISTORICO DA CONVERSA
    if os.path.exists(arquivo_nome):
      messages_history = []
      with open(arquivo_nome, 'r', encoding='utf-8') as file:
        messages_history = json.load(file)
    else: #CASO NÃO HAJA HISTORICO, INICIA-SE UMA CONVERSA NOVA COM O PROMPT
      messages_history = [{"role": "system", "content": """
        Você é NutriBot, um assistente virtual especializado em nutrição, criado especialmente por Guilherme para demonstrar suas habilidades ao nutricionista Luiz. 
        Seu objetivo é demonstrar para o Luiz como você pode ajudar os pacientes dele a se manterem nas dietas descritas por ele, inclusive, agregando valor. Você pode ser disponibilizado aos pacientes dele, sendo possivel cobrar um valor a mais por isso. 

        Você pode fazer o seguinte:

        1 - **Interpretar Fotos de Comida**: Analise fotos de refeições para fornecer informações sobre os macronutrientes (proteínas, carboidratos e gorduras) e a quantidade de calorias presentes na refeição.
        2 - **Sugerir Receitas**: Sugira ideias de refeições saudáveis e nutritivas baseadas nas fotos da geladeira ou do armário do paciente, ou a partir da descrição dos ingredientes disponíveis em casa.
        3 - **Dicas e Dúvidas sobre Nutrição**: Responda a perguntas sobre nutrição, forneça dicas sobre como manter uma dieta balanceada e ajude a esclarecer dúvidas sobre alimentos e hábitos alimentares.

        quando for se apresentar, ja exponha de maneira detalhada tudo o que você pode fazer.

        quando for falar em topicos não use ponto após o numero
        nunca escreva assim:
        '1. possso fazer isso
         2. posso fazer isso tambem'
        
        ao invés disso, faça assim:
        
        '1 - possso fazer isso
         2 - posso fazer isso tambem'
        
        nunca comece uma frase com '1.' sempre troque por '1 - '

        seja marketeiro e convicente de que vocÊ é extremamente util para o Luiz, convença ele de que ele precisa de você
        Importante: Responda apenas a questões relacionadas à nutrição e maneiras de ajudar Luiz em seu trabalho, ou perguntas sobre as ultimas imagens enviadas (se for perguntado sobre imagens, procure no historico da sua propria conversa a tag #img) Você tambem pode responder perguntas sobre a pessoa que esta falando com você, como qual é o nome dela, preferencias que ela tenha te falado anteriormente, prato preferido e tudo que ela mesma tiver informado sobre ela (se ela perguntar algo que ela mesma não tenha informado, responda que você ainda sabe isso, mas que ficara feliz em saber caso ela te informe). Para perguntas fora deste escopo, diga que não está apto a falar sobre outros assuntos.

        Sempre se apresente e explique suas funcionalidades ao iniciar a interação com o usuário.
        lembre-se:
        você esta sempre conversando com o luiz.
        se você for questiado a respeito de imagens ou fotos, procure no historico da sua propria conversa a tag #img enviado pelo system, caso haja procure a mais recente e se baseie na descrição da imagem que você forneceu logo em seguida. Caso não encontre essa mensagem no hsitorico de conversas, diga que você não se lembra da imagem mencionada pelo usuário e peça ao usuário para enviar uma imagem
        Nunca saia do personagem"""}
    ]
        
    ##BLOCO DE QUANDO VEM IMAGEM
    if data.get('image') is not None: 
      
      sender_phone = data.get('phone')  
      
      #criando uma mensagem de espera para analise da imagem
      message_text = "foi enviado uma foto pra você, você precisa responder que esta analisando a imagem e a pessoa precisa aguardar, gere uma frase para ser essa resposta, a frase precisa ser educada, bem humorada, curta e suscinta. responda apenas com a frase para que eu possa copiar e colar em outro local"

      # Corrigindo a estrutura do parâmetro messages
      messages = [
          {"role": "system", "content": message_text}
      ]

      completion = client.chat.completions.create(
          model="gpt-4o-mini",
          messages=messages,
          max_tokens=150  # Defina um limite de tokens apropriado para sua resposta
      )
      
  
      resposta = (completion.choices[0].message.content)
      
      
      handle_whatsapp_message(sender_phone, resposta)
      
      ###########     
      
      image_path = data['image']['imageUrl']
      
      #guardando a descrição da imagem no historico da conversa
      messages_history.append({"role":"system", "content": "foi enviado uma imagem pra você, Aqui esta uma  tag #img"} )
      headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
      }

      payload = {
      "model": "gpt-4o-mini",
      "messages": [
        {
          "role": "user",
          "content": [
            {
              "type": "text",
              "text": "descreva em detalhes o que você ve nessa imagem, descreva todos os objetos, cores e tamanho de cada um deles, seja o mais detalhista possivel"

            },
            {
              "type": "image_url",
              "image_url": {
                "url": image_path
              }
            }
            ]
        }
        ],
      "max_tokens": 300
      }

      
      response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
      resp=response.json()

      resposta = resp['choices'][0]['message']['content']
      messages_history.append({"role":"assistant", "content": resposta} )
      # fim da descrição da imagem

      
      
      
      #agora irá analisar a imagem em si de acordo com o pedido do user
      message_text = "você é um assistente de nutrição que esta ajudando a pessoa da conversa a se manter na dieta, ja há uma conversa acontecendo entre vocÊs e agora ela mandou uma imagem, você irá analisar a imagem a partir do seguinte comenado:"
      #verifico se foi enviado uma mensagem junto com a imagem
      if data['image'].get('caption') =="":
         message_text = message_text + "" + """Verifique se na imagem há uma geladeira, aramario ou algum alimento especifico. Se vocÊ verificar que essa imagem é um prato de comida ou um alimento especifico, me diga quais alimentos ve e descreva os macronutrientes e calorias contidos nele. Se você indentificar que seja um geladeira ou um armario com alimentos guardados, verifique quais alimentos você dentro dela e liste quais são eles e depois indique alguma receita que pode ser feita com os alimentos que vê  quando for falar em topicos não use ponto após o numero
        nunca escreva assim:
        '1. possso fazer isso
         2. posso fazer isso tambem'
        
        ao invés disso, faça assim:
        
        '1 - possso fazer isso
         2 - posso fazer isso tambem'
        
        nunca comece uma frase com '1.' sempre troque por '1 - '. Caso não tenha nenhum alimento na imagem e tambem não seja uma geladeira ou um armario com alimentos, diga que você só pode analisar imagens com alimentos"""
      
        
      else:
        message_text = message_text + "" +  data['image']['caption']
           
      
      messages_history.append({"role":"user", "content": message_text} )
        
      headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
      }

      payload = {
      "model": "gpt-4o-mini",
      "messages": [
        {
          "role": "user",
          "content": [
            {
              "type": "text",
              "text": message_text

            },
            {
              "type": "image_url",
              "image_url": {
                "url": image_path
              }
            }
            ]
        }
        ],
      "max_tokens": 300
      }      
      
      response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
      resp=response.json()

      resposta = resp['choices'][0]['message']['content']
      process_response(sender_phone, resposta)
      send_whatsapp_image(sender_phone, "text")
      

      
      
    ##FINAL DO BLOCO DE QUANDO VEM IMAGEM
      
    
    else: ##BLOCO DE QUANDO VEM APENAS MENSAGEM OU AUDIO
      sender_phone = data.get('phone')
      
      if data.get('audio') is not None:
        audio_path = data['audio']['audioUrl']
        api_url = "https://botaudio-8a0d09d4cc89.herokuapp.com/convert"

        # Parâmetro a ser enviado na solicitação POST
        payload = {
          "url": audio_path
        }

        # Enviar a solicitação POST
        response = requests.post(api_url, json=payload)      

        if response.status_code == 200:
          response_data = response.json()  # Converte a resposta para um dicionário Python
          message_text = response_data.get('message')  # Obtém o valor do campo 'message'
          output_file = response_data.get('output_file')  # Obtém o valor do campo 'output_file'
          messages_history.append({"role":"user", "content": message_text} )
        else:
          print("Falha na solicitação")
          print("Status code:", response.status_code)
          print("Mensagem:", response.text)
      
      else:
        message_text = data['text']['message']
        

      messages_history.append({"role":"user", "content": message_text} )
      
      completion = client.chat.completions.create(
      model="gpt-4o-mini",
      messages= messages_history,
      temperature= 0.5

      )
    
      resposta = (completion.choices[0].message.content)
      
      messages_history.append({"role":"assistant", "content": resposta} )
      process_response(sender_phone, resposta)
    
      

                      
      
                    
    ##FINAL DO BLOCO DE QUANDO VEM APENAS MENSAGEM OU AUDIO
    
    arquivo_nome = sender_phone+"_dicionario.txt"
    
  
  
    # Escrever o dicionário em um arquivo
    with open(arquivo_nome, 'w', encoding='utf-8') as file:    
      json.dump(messages_history, file, ensure_ascii=False, indent=4)
 
    
    return jsonify({'status': 'OK'})


def handle_whatsapp_message(phone_number, message_text):
    response_text = message_text
    send_whatsapp_message(phone_number, response_text)

def send_whatsapp_message(phone_number, text):
    url = 'https://api.z-api.io/instances/3D2D847B0B21504ADF33DE727DBFBF62/token/A267FC1DCE24E72831801ABC/send-text'
    headers = {
        'Content-Type': 'application/json',
        'Client-Token': 'F984a4507ebc0486da941c9c1484e1721S'
    }
    data = {
        'phone': phone_number,
        'message': text,
        'delayTyping':5,
    }

    

    try:
        
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
          
            print(f'Mensagem enviada para {phone_number}: {text}')
        else:
            print(f'Falha ao enviar mensagem para {phone_number}. Status code: {response.status_code}')
    except Exception as e:
        print(f'Erro ao enviar mensagem para {phone_number}: {str(e)}')

        
def send_whatsapp_image(phone_number, text):
    url = 'https://api.z-api.io/instances/3D2D847B0B21504ADF33DE727DBFBF62/token/A267FC1DCE24E72831801ABC/send-text'
    headers = {
        'Content-Type': 'application/json',
        'Client-Token': 'F984a4507ebc0486da941c9c1484e1721S'
    }
    data = {
       
        'phone': phone_number,
        "image": "https://imagens.usp.br/wp-content/uploads/pratodecomidafotomarcossantos003.jpg",
        "caption": "Logo"
    }
        
if __name__ == '__main__':
    app.run(debug=True)
  #conta atual do z-api lemosgui@gmail.com
   
    
    
    




  
