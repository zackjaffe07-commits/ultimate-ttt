from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import joinedload
from game.logic import UltimateTicTacToe
import random, string, os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'landing'

games = {}
guest_games = {}
active_players = set()

# --- Models and User Loading ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    loser_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_draw = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    winner = db.relationship('User', foreign_keys=[winner_id], backref='won_matches')
    loser = db.relationship('User', foreign_keys=[loser_id], backref='lost_matches')

class GuestUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id
        self.username = f"Guest_{user_id[:5]}"
    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    def get_id(self): return self.id

@login_manager.user_loader
def load_user(user_id):
    if session.get('is_guest'): return GuestUser(session.get('guest_id'))
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/')
def landing(): return render_template('landing.html')
@app.route('/rules')
def rules(): return render_template('rules.html')
@app.route('/guest')
def guest_login():
    if 'guest_id' not in session: session['guest_id'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    session['is_guest'] = True
    user = GuestUser(session['guest_id']); login_user(user)
    return redirect(url_for('home'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and not session.get('is_guest'): return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user is None or not user.check_password(request.form['password']):
            flash('Invalid username or password'); return redirect(url_for('login'))
        login_user(user)
        session.pop('is_guest', None); session.pop('guest_id', None)
        return redirect(url_for('home'))
    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and not session.get('is_guest'): return redirect(url_for('home'))
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Username already exists'); return redirect(url_for('register'))
        new_user = User(username=request.form['username']); new_user.set_password(request.form['password'])
        db.session.add(new_user); db.session.commit()
        login_user(new_user)
        session.pop('is_guest', None); session.pop('guest_id', None)
        return redirect(url_for('home'))
    return render_template('register.html')
@app.route('/logout')
@login_required
def logout():
    logout_user(); session.clear()
    return redirect(url_for('landing'))
@app.route("/home")
@login_required
def home(): return render_template("home.html", is_guest=session.get('is_guest', False))
@app.route("/game/<room>")
@login_required
def game(room):
    active_games = get_active_games()
    if room not in active_games: return render_template("home.html", error="Invalid room code")
    return render_template("game.html", room=room)
@app.route("/profile")
@login_required
def profile():
    if session.get('is_guest'): flash("Guests do not have profiles."); return redirect(url_for('home'))
    matches = Match.query.filter((Match.winner_id == current_user.id) | (Match.loser_id == current_user.id)).order_by(Match.timestamp.desc()).all()
    return render_template("profile.html", user=current_user, matches=matches)

# --- Helper Functions ---
def new_room(): return ''.join(random.choices(string.ascii_lowercase, k=5))
def get_active_games(): return guest_games if session.get('is_guest') else games

def emit_game_status(room):
    game_data = get_active_games().get(room)
    if game_data:
        status_data = {
            'player_count': len(game_data['player_accounts']),
            'ready_players': [p['username'] for s, p in game_data['players'].items() if s in game_data.get('ready', set())],
            'rematch_players': [p['username'] for s, p in game_data['players'].items() if s in game_data.get('rematchReady', set())]
        }
        emit('gameStatus', status_data, room=room)

def emit_spectator_list(room):
    game_data = get_active_games().get(room)
    if game_data:
        spectator_list = [spec['username'] for spec in game_data.get('spectators', {}).values()]
        emit('spectatorList', {'spectators': spectator_list}, room=room)

# --- SocketIO Events ---
@socketio.on("create")
@login_required
def create():
    if current_user.get_id() in active_players:
        emit('already_in_game', {'error': 'You are already in a game.'}); return
    active_games = get_active_games()
    room = new_room()
    active_games[room] = { "game": UltimateTicTacToe(), "player_accounts": {}, "players": {}, "spectators": {}, "ready": set(), "rematchReady": set(), "chat_history": [] }
    emit("created", room)

@socketio.on("join")
@login_required
def join(data):
    active_games = get_active_games()
    room = data["room"]; sid = request.sid
    game_data = active_games.get(room)
    if not game_data: emit("invalid"); return
    user_id = current_user.get_id()
    is_locked_player = user_id in game_data.get("player_accounts", {}).values()
    if not is_locked_player and user_id in active_players:
        emit('already_in_game', {'error': 'You are already in another game.'}); return
    join_room(room)
    players = game_data["players"]
    player_accounts = game_data["player_accounts"]
    if is_locked_player:
        symbol = next(s for s, uid in player_accounts.items() if uid == user_id)
        old_sid = next((s for s, p in players.items() if p.get('user_id') == user_id), None)
        if old_sid: del players[old_sid]
        players[sid] = {"symbol": symbol, "user_id": user_id, "username": current_user.username}
        emit("assign", symbol)
    elif len(player_accounts) < 2:
        symbol = "X" if "X" not in player_accounts else "O"
        player_accounts[symbol] = user_id
        players[sid] = {"symbol": symbol, "user_id": user_id, "username": current_user.username}
        active_players.add(user_id)
        emit("assign", symbol)
    else:
        game_data["spectators"][sid] = {"user_id": user_id, "username": current_user.username}
        emit("spectator")
    if game_data.get("chat_history"): emit('chatHistory', {'history': game_data["chat_history"]})
    emit("state", game_data["game"].state(), room=room)
    emit_game_status(room)
    emit_spectator_list(room)

def record_match(game_data, winner_symbol):
    for user_id in game_data["player_accounts"].values(): active_players.discard(user_id)
    if session.get('is_guest') or len(game_data["player_accounts"]) < 2: return
    p1_id = game_data["player_accounts"]["X"]; p2_id = game_data["player_accounts"]["O"]
    p1 = User.query.get(p1_id); p2 = User.query.get(p2_id)
    if not p1 or not p2: return
    if winner_symbol == "D": match = Match(winner=p1, loser=p2, is_draw=True)
    else:
        winner_id = game_data["player_accounts"][winner_symbol]
        loser_symbol = "X" if winner_symbol == "O" else "O"
        loser_id = game_data["player_accounts"][loser_symbol]
        match = Match(winner_id=winner_id, loser_id=loser_id, is_draw=False)
    db.session.add(match); db.session.commit()

@socketio.on("ready")
@login_required
def ready(data):
    active_games = get_active_games(); room = data["room"]; sid = request.sid
    game_data = active_games.get(room)
    if not game_data or sid not in game_data["players"]: return
    game_data["ready"].add(sid)
    emit_game_status(room)
    if len(game_data["player_accounts"]) == 2 and len(game_data["ready"]) == 2:
        game_data["game"].started = True
        emit("state", game_data["game"].state(), room=room)

@socketio.on("rematch")
@login_required
def rematch(data):
    active_games = get_active_games(); room = data["room"]; sid = request.sid
    game_data = active_games.get(room)
    if not game_data or sid not in game_data["players"]: return
    game_data["rematchReady"].add(sid)
    emit_game_status(room)
    if len(game_data["rematchReady"]) == 2:
        player_accounts = game_data["player_accounts"]
        # Reset the game for the same players
        active_games[room] = {
            "game": UltimateTicTacToe(),
            "player_accounts": player_accounts,
            "players": game_data["players"], # Keep current player sessions
            "spectators": game_data["spectators"],
            "ready": set(),
            "rematchReady": set(),
            "chat_history": game_data["chat_history"]
        }
        emit("rematchAgreed", room=room)

@socketio.on('disconnect')
def disconnect():
    sid = request.sid
    for g in [games, guest_games]:
        for room, game_data in list(g.items()):
            if sid in game_data.get("players", {}):
                del game_data["players"][sid]
                emit_game_status(room)
                return
            elif sid in game_data.get("spectators", {}):
                del game_data["spectators"][sid]
                leave_room(room)
                emit_spectator_list(room)
                emit_game_status(room)
                return

@socketio.on('chat')
@login_required
def chat(data):
    room = data['room']; message = data['message']; username = current_user.username
    game_data = get_active_games().get(room)
    if not game_data: return
    is_spectator = request.sid in game_data['spectators']
    chat_entry = {'username': username, 'message': message, 'is_spectator': is_spectator}
    game_data["chat_history"].append(chat_entry)
    emit('chatMessage', chat_entry, room=room)

@socketio.on("move")
@login_required
def move(data):
    game_data = get_active_games().get(data["room"])
    if not game_data: return
    game = game_data["game"]
    if game.make_move(data["board"], data["cell"]):
        if game.game_winner: record_match(game_data, game.game_winner)
        emit("state", game.state(), room=data["room"])

@socketio.on("resign")
@login_required
def resign(data):
    game_data = get_active_games().get(data["room"])
    if not game_data: return
    game = game_data["game"]; loser_symbol = data["symbol"]
    winner_symbol = "X" if loser_symbol == "O" else "O"
    game.resign(loser_symbol)
    record_match(game_data, winner_symbol)
    emit("state", game.state(), room=data["room"])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
