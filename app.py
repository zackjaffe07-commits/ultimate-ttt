from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from game.logic import UltimateTicTacToe
import random, string, os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

games = {}

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    loser_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_draw = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    winner = db.relationship('User', foreign_keys=[winner_id], backref='won_matches')
    loser = db.relationship('User', foreign_keys=[loser_id], backref='lost_matches')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return 'Username already exists'
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/")
@login_required
def home():
    return render_template("home.html")

@app.route("/game/<room>")
@login_required
def game(room):
    if room not in games:
        return render_template("home.html", error="Invalid room code")
    return render_template("game.html", room=room)

@app.route("/profile")
@login_required
def profile():
    # Eager load matches to prevent N+1 query issues
    user = User.query.options(db.joinedload('won_matches'), db.joinedload('lost_matches')).get(current_user.id)
    return render_template("profile.html", user=user)

def new_room():
    return ''.join(random.choices(string.ascii_lowercase, k=5))

# SocketIO Events
@socketio.on("create")
def create():
    room = new_room()
    games[room] = {
        "game": UltimateTicTacToe(),
        "players": {},
        "spectators": set(),
        "ready": set(),
        "rematchReady": set()
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

    # Use a persistent user ID from the session
    user_id = current_user.get_id()

    if user_id not in [p_data['user_id'] for p_data in players.values()] and len(players) >= 2:
        game_data["spectators"].add(sid)
        emit("spectator")
    elif user_id not in [p_data['user_id'] for p_data in players.values()]:
        symbol = "X" if len(players) == 0 else "O"
        players[sid] = {"symbol": symbol, "user_id": user_id, "username": current_user.username}
        emit("assign", symbol)

    emit("state", game_data["game"].state(), room=room)
    emit("spectatorCount", len(game_data["spectators"]), room=room)

def record_match(game_data, winner_symbol):
    if len(game_data["players"]) != 2:
        return

    player_data = list(game_data["players"].values())
    
    if winner_symbol == "D":
        winner, loser = None, None
        is_draw = True
    else:
        winner_data = next(p for p in player_data if p['symbol'] == winner_symbol)
        loser_data = next(p for p in player_data if p['symbol'] != winner_symbol)
        winner = User.query.get(winner_data['user_id'])
        loser = User.query.get(loser_data['user_id'])
        is_draw = False

    match = Match(winner=winner, loser=loser, is_draw=is_draw)
    db.session.add(match)
    db.session.commit()

@socketio.on("move")
def move(data):
    room = data["room"]
    game_data = games[room]
    game = game_data["game"]

    if game.make_move(data["board"], data["cell"]):
        if game.game_winner:
            record_match(game_data, game.game_winner)
        emit("state", game.state(), room=room)

@socketio.on("resign")
def resign(data):
    room = data["room"]
    game_data = games[room]
    game = game_data["game"]
    
    loser_symbol = data["symbol"]
    winner_symbol = "X" if loser_symbol == "O" else "O"
    
    game.resign(loser_symbol)
    record_match(game_data, winner_symbol)
    emit("state", game.state(), room=room)

@socketio.on("rematch")
def rematch(data):
    room = data["room"]
    sid = data["sid"]

    games[room]["rematchReady"].add(sid)

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
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
