# import gradio as gr
# import sys
# import requests


# API_KEY = 'ragflow-I4ZWM0MjIyMjNiMzExZWY5ZGExMDI0Mm'
# headers = {
#     'Authorization': 'Bearer ' + API_KEY
# }
# URL = 'http://12.1.52.177:81/v1/api/'
# NEW_CONV_URL = URL + 'new_conversation?user_id='
# COMPLETION_URL = URL + 'completion'

# user_id = 'Larry'
# conv_id = ''

# def response(message, history):
#     global conv_id
#     if len(history) < 1:
#         conv_id = ''
#         r = requests.get(NEW_CONV_URL+user_id, headers=headers)
#         conv_id = r.json()['data']['id']
#     post_data = {
#         'conversation_id': conv_id,
#         'messages': [{
#             'role': 'user',
#             'content': message
#         }],
#         'stream': False
#     }
#     response = requests.post(COMPLETION_URL, json=post_data, headers=headers)
#     print(response.text)
#     return response.json()['data']['answer']

# gr.ChatInterface(response).launch(server_name='0.0.0.0', server_port=7869)
