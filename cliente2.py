import grpc
import messenger_pb2
import messenger_pb2_grpc
import threading

def connect(server_address, client_name):
    channel = grpc.insecure_channel(server_address)
    stub = messenger_pb2_grpc.MessengerStub(channel) #stub. Um stub é uma representação do servidor com o qual estamos nos comunicando.
    response = stub.Connect(messenger_pb2.ClientInfo(name=client_name))
    return response.connected, stub

def show_menu(stub):
    response = stub.ShowMenu(messenger_pb2.Empty())
    print(response.menu)

def choose_category(stub, client_name, choice):
    stub.ChooseCategory(messenger_pb2.CategoryChoice(name=client_name, choice=choice))

def choose_item(stub, client_name, item):
    stub.ChooseItem(messenger_pb2.ItemChoice(name=client_name, item=item))

def send_message(stub, sender, receiver, content):
    stub.SendMessage(messenger_pb2.Message(sender=sender, receiver=receiver, content=content))

#stub permite para comunicação com o servidor
#message_event: Um evento para sinalizar quando uma mensagem é recebida.
#question_event: Um evento para sinalizar quando uma pergunta é feita.
def receive_messages(stub, client_name, is_questioner, message_event, question_event):
    for message in stub.ReceiveMessages(messenger_pb2.ClientInfo(name=client_name)):
        if "Categoria escolhida" in message.content: #verifica se a substring "Categoria escolhida" está presente no conteúdo da mensagem recebida message
            print(f"\n{message.content}")
            if not is_questioner:
                item = input("Escolha um item da categoria: ")
                choose_item(stub, client_name, item)
        elif "O outro jogador escolheu um item" in message.content:
            print(f"\n{message.content}")
            if is_questioner:
                message_event.set()  # Sinaliza que o cliente pode começar a fazer perguntas
            else:
                print("Esperando perguntas do outro jogador...")
        elif "adivinhou corretamente" in message.content or "adivinhou incorretamente" in message.content:
            print(f"\n{message.content}")
        else:
            print(f"\nMensagem recebida do cliente {message.sender}: {message.content}")
            if not is_questioner:
                answer = input("\nDigite 'sim' ou 'não' para responder (ou 'sair' para sair): ")
                send_message(stub, client_name, message.sender, answer)
            question_event.set()  # Sinaliza que a resposta foi recebida

def main():
    server_address = 'localhost:50051'
    client_name = input("Digite seu nome: ")

    connected, stub = connect(server_address, client_name)
    if connected:
        print(f"{client_name} conectado ao servidor!")
        
        # Define quem vai começar fazendo perguntas
        is_questioner = input("Você vai advinhar a palavra? (sim/não): ").strip().lower() == 'sim'
        
        message_event = threading.Event()
        question_event = threading.Event()
        threading.Thread(target=receive_messages, args=(stub, client_name, is_questioner, message_event, question_event)).start()

        if is_questioner:
            print("Esperando o outro jogador escolher a categoria e o item...")
            message_event.wait()  # Espera até que o outro jogador escolha a categoria e o item
            
            for _ in range(3):  # Permite até 5 perguntas
                question = input("Faça sua pergunta (ou 'sair' para sair): ")
                if question.lower() == 'sair':
                    break
                receiver = input("Digite o nome do destinatário: ")
                send_message(stub, client_name, receiver, question)
                question_event.clear() # Reseta o evento antes de esperar pela próxima pergunta
                question_event.wait()  # Espera até que a resposta seja recebida
                
            # Tentativa de adivinhar o item escolhido pelo outro jogador
            guess = input("Adivinhe o item escolhido pelo outro jogador: ")
            send_message(stub, client_name, receiver, f"Tentativa de adivinhação: {guess}")
        else:
            show_menu(stub)
            choice = input("Escolha uma opção do menu: ")
            choose_category(stub, client_name, choice)
            item = input("Escolha um item da categoria: ")
            choose_item(stub, client_name, item)
            print("Esperando perguntas do outro jogador...")
        
    else:
        print("Falha ao conectar ao servidor.")

if __name__ == '__main__':
    main()