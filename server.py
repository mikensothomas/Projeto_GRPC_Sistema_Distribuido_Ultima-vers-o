from concurrent import futures
import grpc
import messenger_pb2
import messenger_pb2_grpc
from queue import Queue
import threading

class MessengerServicer(messenger_pb2_grpc.MessengerServicer):
    def __init__(self):
        self.clients = {}
        self.categories = {
            "1": "aparelho eletrônico",
            "2": "veículo terrestre",
            "3": "animal"
        }
        self.player_categories = {}
        self.player_choices = {}
        self.message_queues = {}
        self.scores = {}
        self.game_active = True

    def Connect(self, request, context):
        if not self.game_active:
            return messenger_pb2.ConnectionStatus(connected=False)
        
        client_name = request.name
        self.clients[client_name] = context
        self.message_queues[client_name] = Queue()
        self.scores[client_name] = 0
        print(f"Cliente {client_name} conectado.")
        return messenger_pb2.ConnectionStatus(connected=True)

    def ShowMenu(self, request, context):
        menu = "Escolha a categoria de palavras:\n"
        for key, category in self.categories.items():
            menu += f"{key}) {category}\n"
        return messenger_pb2.Menu(menu=menu)

    def ChooseCategory(self, request, context):
        if not self.game_active:
            return messenger_pb2.Empty()
        
        client_name = request.name
        choice = request.choice
        if choice in self.categories:
            category = self.categories[choice]
            self.player_categories[client_name] = category
            print(f"Cliente {client_name} escolheu a categoria: {category}")
            for other_client in self.clients:
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
        print(f"Cliente {client_name} escolheu o item: {item}")
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
        
        receiver = request.receiver
        sender = request.sender
        content = request.content
        if receiver in self.clients:
            if content.startswith("Tentativa de adivinhação: "):
                guess = content[len("Tentativa de adivinhação: "):]
                correct_item = self.player_choices.get(receiver, "")
                if guess == correct_item:
                    self.scores[sender] += 1
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
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messenger_pb2_grpc.add_MessengerServicer_to_server(MessengerServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Servidor conectado na porta 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
