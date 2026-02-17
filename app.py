from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
from game.logic import UltimateTicTacToe
import random, string

app = Flask(__name__)
socketio = SocketIO(app)
games = {}

def new_room():
    return ''.join(random.choices(string.ascii_lowercase, k=5))

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/game/<room>")
def game(room):
    if room not in games:
        return render_template("home.html", error="Invalid room code")
    return render_template("game.html", room=room)

@socketio.on("create")
def create():
    room = new_room()
    games[room] = {
        "game": UltimateTicTacToe(),
        "players": {},         # sid -> symbol
        "spectators": set(),   # sid
        "ready": set(),        # sids ready to start
        "rematchReady": set()  # sids ready to rematch
    }
    emit("created", room)

@socketio.on("join")
def join(data):
    room = data["room"]
    sid = data["sid"]

    if room not in games:
        emit("invalid")
        return

    join_room(room)
    game_data = games[room]
    players = game_data["players"]

    if sid not in players and len(players) >= 2:
        game_data["spectators"].add(sid)
        emit("spectator")
    elif sid not in players:
        players[sid] = "X" if len(players) == 0 else "O"

    if sid in players:
        emit("assign", players[sid])

    emit("state", game_data["game"].state(), room=room)
    emit("spectatorCount", len(game_data["spectators"]), room=room)


@socketio.on('disconnect')
def disconnect():
    sid = request.sid
    for room, game_data in games.items():
        if sid in game_data["spectators"]:
            game_data["spectators"].remove(sid)
            leave_room(room)
            emit("spectatorCount", len(game_data["spectators"]), room=room)
            break
        # Player disconnects are handled by the client-side refresh logic
        # so we don't need to do anything here for players.


@socketio.on("ready")
def ready(data):
    room = data["room"]
    sid = data["sid"]
    games[room]["ready"].add(sid)

    # Start only when 2 players ready
    if len(games[room]["ready"]) == 2:
        games[room]["game"].started = True
        emit("state", games[room]["game"].state(), room=room)

@socketio.on("move")
def move(data):
    room = data["room"]
    game = games[room]["game"]

    if game.make_move(data["board"], data["cell"]):
        emit("state", game.state(), room=room)

@socketio.on("resign")
def resign(data):
    room = data["room"]
    loser = data["symbol"]
    game = games[room]["game"]
    game.resign(loser)  # player who clicked resign loses
    emit("state", game.state(), room=room)

@socketio.on("rematch")
def rematch(data):
    room = data["room"]
    sid = data["sid"]

    games[room]["rematchReady"].add(sid)

    # Only start rematch when BOTH players agree
    if len(games[room]["rematchReady"]) == 2:
        old_players = games[room]["players"]
        spectators = games[room]["spectators"]

        games[room] = {
            "game": UltimateTicTacToe(),
            "players": old_players,
            "spectators": spectators,
            "ready": set(),
            "rematchReady": set()
        }

        emit("state", games[room]["game"].state(), room=room)
        emit("rematchStarted", room=room)

if __name__ == "__main__":
    socketio.run(app, debug=True)