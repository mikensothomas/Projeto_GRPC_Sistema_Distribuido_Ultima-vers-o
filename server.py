from concurrent import futures #execução assíncrona
import grpc
import messenger_pb2
import messenger_pb2_grpc
from queue import Queue #Éusada para armazenar mensagens recebidas.
import threading #aceitar múltiplas conexões de clientes ao mesmo tempo

class MessengerServicer(messenger_pb2_grpc.MessengerServicer):
    def __init__(self): #self refere-se à instância da classe que está sendo criada.
        self.clients = {}
        self.categories = {
            "1": "aparelhos eletrônicos",
            "2": "veículos terrestres",
            "3": "animais"
        }
        self.player_categories = {}
        self.player_choices = {}
        self.message_queues = {}
        self.scores = {}
        self.game_active = True

    def Connect(self, request, context):
        if not self.game_active:
            return messenger_pb2.ConnectionStatus(connected=False)
        
        client_name = request.name #Obtendo o Nome do Cliente
        self.clients[client_name] = context #Registrando o Cliente
        self.message_queues[client_name] = Queue() #Criando uma Fila de Mensagens para o Cliente
        self.scores[client_name] = 0 #Inicializando a Pontuação do Cliente:
        print(f"Cliente {client_name} conectado.")
        return messenger_pb2.ConnectionStatus(connected=True)

    def ShowMenu(self, request, context):
        menu = "Escolha uma categoria:\n"
        for key, category in self.categories.items(): #Para cada categoria, concatena a chave e o valor ao menu, formatando-os em uma string.
            menu += f"{key}) {category}\n"
        return messenger_pb2.Menu(menu=menu) #Retornando o Menu para o Cliente

    def ChooseCategory(self, request, context):
        if not self.game_active:
            return messenger_pb2.Empty() #retorna uma mensagem vazia 
        
        client_name = request.name #Obtendo o Nome do Cliente
        choice = request.choice  #Obtendo a escolha do Cliente
        if choice in self.categories:  #Verifica se a escolha do cliente está entre as categorias disponíveis.
            category = self.categories[choice]
            self.player_categories[client_name] = category #Armazenando a Categoria Escolhida pelo Cliente
            print(f"Cliente {client_name} escolheu a categoria: {category}") #para o servidor
            for other_client in self.clients: #Para cada outro cliente, adiciona uma mensagem à sua fila de mensagens.
                if other_client != client_name:
                    self.message_queues[other_client].put(messenger_pb2.Message(
                        sender=client_name,
                        content=f"Categoria escolhida pelo outro jogador: {category}"
                    ))
        else:
            print(f"Escolha inválida.")
        return messenger_pb2.Empty()

    def ChooseItem(self, request, context):
        if not self.game_active:
            return messenger_pb2.Empty()
        
        client_name = request.name
        item = request.item
        self.player_choices[client_name] = item
        print(f"Cliente {client_name} escolheu o item: {item}") #para o servidor
        for other_client in self.clients:
            if other_client != client_name:
                self.message_queues[other_client].put(messenger_pb2.Message(
                    sender=client_name,
                    content="O outro jogador escolheu um item. Você pode começar a fazer perguntas."
                ))
        return messenger_pb2.Empty()

    def SendMessage(self, request, context):
        if not self.game_active:
            return messenger_pb2.Empty()
        
        receiver = request.receiver #responde as perguntas
        sender = request.sender #Fazer as perguntas
        content = request.content
        if receiver in self.clients: #Verifica se o destinatário está na lista de clientes conectados.
            if content.startswith("Tentativa de adivinhação: "): #Verifica se o conteúdo da mensagem começa com a string indicativa de uma tentativa de adivinhação.
                guess = content[len("Tentativa de adivinhação: "):]
                correct_item = self.player_choices.get(receiver, "")
                if guess == correct_item:
                    #self.scores[sender] += 1
                    result_message = f"{sender} adivinhou corretamente! Ele(a) venceu e o {receiver} perdeu."
                else:
                    result_message = f"{sender} adivinhou incorretamente ele perdeu e o {receiver} venceu."
                for client in self.clients:
                    self.message_queues[client].put(messenger_pb2.Message(
                        sender=sender,
                        content=result_message
                    ))
                # Termina o jogo após uma adivinhação
                self.EndGame(messenger_pb2.Empty(), context)
            else:
                message = messenger_pb2.Message(sender=sender, receiver=receiver, content=content)
                self.message_queues[receiver].put(message)
                print(f"Mensagem enviada de {sender} para {receiver}")
            return messenger_pb2.Empty()
        else:
            print(f"Destinatário {receiver} não encontrado.")
            return messenger_pb2.Empty()

    def ReceiveMessages(self, request, context):
        client_name = request.name
        while self.game_active:
            if client_name in self.message_queues:
                message = self.message_queues[client_name].get()
                yield message

    def EndGame(self, request, context):
        self.game_active = False
        for client in self.clients:
            self.message_queues[client].put(messenger_pb2.Message(
                sender="Server",
                content="O jogo acabou."
            ))
        print("O jogo acabou. Desconectando todos os clientes.")
        threading.Timer(1.0, self._shutdown_server).start()  # Atraso para permitir que as mensagens sejam enviadas
        return messenger_pb2.Empty()

    def _shutdown_server(self):
        global server
        server.stop(0)
        print("Servidor encerrado.")

def serve():
    global server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10)) # Criar um servidor grpc
    messenger_pb2_grpc.add_MessengerServicer_to_server(MessengerServicer(), server) #Este comando registra a classe MessengerServicer
    server.add_insecure_port('127.0.0.1:50051')
    server.start()
    print("Servidor conectado na porta 50051")
    server.wait_for_termination() #Mantém o servidor em execução indefinidamente até que seja explicitamente parado.

if __name__ == '__main__':
    serve()