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
    if session.get('is_guest'):
        return GuestUser(session.get('guest_id'))
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/guest')
def guest_login():
    if 'guest_id' not in session:
        session['guest_id'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    session['is_guest'] = True
    user = GuestUser(session['guest_id'])
    login_user(user)
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and not session.get('is_guest'):
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user)
        session.pop('is_guest', None)
        session.pop('guest_id', None)
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and not session.get('is_guest'):
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        session.pop('is_guest', None)
        session.pop('guest_id', None)
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('landing'))

@app.route("/home")
@login_required
def home():
    return render_template("home.html", is_guest=session.get('is_guest', False))

@app.route("/game/<room>")
@login_required
def game(room):
    active_games = guest_games if session.get('is_guest') else games
    if room not in active_games:
        return render_template("home.html", error="Invalid room code")
    return render_template("game.html", room=room)

@app.route("/profile")
@login_required
def profile():
    if session.get('is_guest'):
        flash("Guests do not have profiles.")
        return redirect(url_for('home'))
    matches = Match.query.filter(
        (Match.winner_id == current_user.id) | (Match.loser_id == current_user.id)
    ).order_by(Match.timestamp.desc()).all()
    return render_template("profile.html", user=current_user, matches=matches)

def new_room():
    return ''.join(random.choices(string.ascii_lowercase, k=5))

def get_active_games():
    return guest_games if session.get('is_guest') else games

# SocketIO Events
@socketio.on("create")
@login_required
def create():
    active_games = get_active_games()
    room = new_room()
    active_games[room] = {
        "game": UltimateTicTacToe(), "players": {}, "spectators": set(),
        "ready": set(), "rematchReady": set()
    }
    emit("created", room)

@socketio.on("join")
@login_required
def join(data):
    active_games = get_active_games()
    room = data["room"]
    sid = request.sid
    game_data = active_games.get(room)
    if not game_data:
        emit("invalid"); return

    join_room(room)
    players = game_data["players"]
    user_id = current_user.get_id()
    
    # Find if user is already in the game (reconnecting)
    old_sid = next((s for s, p in players.items() if p.get('user_id') == user_id), None)

    if old_sid:
        # Player is rejoining, update their sid
        if old_sid != sid:
            players[sid] = players.pop(old_sid)
        emit("assign", players[sid]["symbol"])
    else:
        # New player is joining
        if len(players) < 2:
            symbol = "X" if len(players) == 0 else "O"
            players[sid] = {"symbol": symbol, "user_id": user_id, "username": current_user.username}
            emit("assign", symbol)
        else:
            game_data["spectators"].add(sid)
            emit("spectator")

    emit("state", game_data["game"].state(), room=room)
    emit("spectatorCount", len(game_data["spectators"]), room=room)

def record_match(game_data, winner_symbol):
    if session.get('is_guest') or len(game_data["players"]) < 2: return
    player_list = list(game_data["players"].values())
    p1 = User.query.get(player_list[0]['user_id'])
    p2 = User.query.get(player_list[1]['user_id'])

    if not p1 or not p2: return # Ensure both players are actual users

    if winner_symbol == "D":
        match = Match(winner=p1, loser=p2, is_draw=True)
    else:
        winner_data = next(p for p in player_list if p['symbol'] == winner_symbol)
        loser_data = next(p for p in player_list if p['symbol'] != winner_symbol)
        winner = User.query.get(winner_data['user_id'])
        loser = User.query.get(loser_data['user_id'])
        match = Match(winner=winner, loser=loser, is_draw=False)
    
    db.session.add(match)
    db.session.commit()

@socketio.on("ready")
@login_required
def ready(data):
    active_games = get_active_games()
    room = data["room"]
    sid = request.sid
    game_data = active_games.get(room)
    if not game_data or sid not in game_data["players"]: return

    game_data["ready"].add(sid)
    if len(game_data["ready"]) == 2:
        game_data["game"].started = True
        emit("state", game_data["game"].state(), room=room)

@socketio.on("move")
@login_required
def move(data):
    active_games = get_active_games()
    room = data["room"]
    game_data = active_games.get(room)
    if not game_data: return
    game = game_data["game"]

    if game.make_move(data["board"], data["cell"]):
        if game.game_winner:
            record_match(game_data, game.game_winner)
        emit("state", game.state(), room=room)

@socketio.on("resign")
@login_required
def resign(data):
    active_games = get_active_games()
    room = data["room"]
    game_data = active_games.get(room)
    if not game_data: return
    game = game_data["game"]
    
    loser_symbol = data["symbol"]
    winner_symbol = "X" if loser_symbol == "O" else "O"
    
    game.resign(loser_symbol)
    record_match(game_data, winner_symbol)
    emit("state", game.state(), room=room)

@socketio.on("rematch")
@login_required
def rematch(data):
    active_games = get_active_games()
    room = data["room"]
    sid = request.sid
    game_data = active_games.get(room)
    if not game_data: return

    game_data["rematchReady"].add(sid)
    if len(game_data["rematchReady"]) == 2:
        old_players = game_data["players"]
        spectators = game_data["spectators"]
        active_games[room] = {
            "game": UltimateTicTacToe(), "players": old_players,
            "spectators": spectators, "ready": set(), "rematchReady": set()
        }
        emit("state", active_games[room]["game"].state(), room=room)
        emit("rematchStarted", room=room)

@socketio.on('disconnect')
def disconnect():
    sid = request.sid
    for g in [games, guest_games]:
        for room, game_data in list(g.items()):
            # Handle player leaving
            if sid in game_data["players"]:
                # For simplicity, we can end the game if a player disconnects.
                # A more advanced implementation could allow reconnection for a short period.
                pass # The robust join logic now handles reconnection.

            # Handle spectator leaving
            if sid in game_data["spectators"]:
                game_data["spectators"].remove(sid)
                leave_room(room)
                emit("spectatorCount", len(game_data["spectators"]), room=room)
                break

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
