import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import text

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Player(db.Model):
    name = db.Column(db.String(100), primary_key=True)
    wins = db.Column(db.Integer, default=0)
    ties = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    
    @property
    def total_games(self):
        return self.wins + self.ties + self.losses
    
    @property
    def win_rate(self):
        if self.total_games == 0:
            return 0.0
        return round((self.wins / self.total_games) * 100, 2)

def validate_choice(choice):
    valid_choices = ['rock', 'paper', 'scissors']
    return choice.lower() in valid_choices

def determine_winner(choice1, choice2):
    choice1, choice2 = choice1.lower(), choice2.lower()
    
    if choice1 == choice2:
        return 'tie'
    
    # rock beats scissors, scissors beats paper, paper beats rock
    winning_combinations = {
        ('rock', 'scissors'): 'player1',
        ('scissors', 'paper'): 'player1', 
        ('paper', 'rock'): 'player1',
        ('scissors', 'rock'): 'player2',
        ('paper', 'scissors'): 'player2',
        ('rock', 'paper'): 'player2'
    }
    
    return winning_combinations.get((choice1, choice2), 'tie')

def get_or_create (name):
    """Get existing player or create new one with default stats"""
    player = Player.query.get(name)
    if not player:
        player = Player(name=name, wins=0, ties=0, losses=0)
        db.session.add(player)
    return player

@app.route('/players', methods=['GET'])
def list_players():
    """Get all players ordered by wins"""
    try:
        players = Player.query.order_by(Player.wins.desc()).all()
        return jsonify([{
            'name': p.name,
            'wins': p.wins,
            'ties': p.ties,
            'losses': p.losses,
            'total_games': p.total_games,
            'win_rate': p.win_rate,
        } for p in players])
    except Exception as e:
        return jsonify({'error': 'Failed to fetch players'}), 500

@app.route('/play', methods=['POST'])
def play():
    """Play a Rock Paper Scissors game"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        required_fields = ['p1_name', 'p2_name', 'p1_choice', 'p2_choice']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        p1_name = data['p1_name'].strip()
        p2_name = data['p2_name'].strip()
        player1_choice = data['p1_choice']
        player2_choice = data['p2_choice']
        
        if not p1_name or not p2_name:
            return jsonify({'error': 'Player names cannot be empty'}), 400
            
        if p1_name == p2_name:
            return jsonify({'error': 'Players must have different names'}), 400
        
        if not validate_choice(player1_choice):
            return jsonify({'error': f'Invalid choice for player 1: {player1_choice}'}), 400
        if not validate_choice(player2_choice):
            return jsonify({'error': f'Invalid choice for player 2: {player2_choice}'}), 400

        player1 = get_or_create(p1_name)
        player2 = get_or_create(p2_name)

        result = determine_winner(player1_choice, player2_choice)
        
        if result == 'tie':
            outcome = "Tie"
            winner_name = None
            player1.ties += 1
            player2.ties += 1
        elif result == 'player1':
            outcome = f"{player1.name} wins"
            winner_name = player1.name
            player1.wins += 1
            player2.losses += 1
        else: 
            outcome = f"{player2.name} wins"
            winner_name = player2.name
            player2.wins += 1
            player1.losses += 1
        
        db.session.commit()
        
        return jsonify({
            'outcome': outcome,
            'winner_name': winner_name,
            'player1': {
                'name': player1.name,
                'choice': player1_choice.lower(),
                'wins': player1.wins,
                'ties': player1.ties,
                'losses': player1.losses
            },
            'player2': {
                'name': player2.name,
                'choice': player2_choice.lower(),
                'wins': player2.wins,
                'ties': player2.ties,
                'losses': player2.losses
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get top 10 players by wins"""
    try:
        players = Player.query.order_by(Player.wins.desc()).limit(10).all()
        return jsonify([{
            'rank': idx + 1,
            'name': p.name,
            'wins': p.wins,
            'ties': p.ties,
            'losses': p.losses,
            'total_games': p.total_games,
            'win_rate': p.win_rate
        } for idx, p in enumerate(players)])
    except Exception as e:
        return jsonify({'error': 'Failed to fetch leaderboard'}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    try:
        total_players = Player.query.count()
        total_games = db.session.query(db.func.sum(Player.wins + Player.ties + Player.losses)).scalar() or 0
        total_games = total_games // 2  
        total_wins = db.session.query(db.func.sum(Player.wins)).scalar() or 0
        total_ties = db.session.query(db.func.sum(Player.ties)).scalar() or 0
        total_ties = total_ties // 2  
        
        return jsonify({
            'total_players': total_players,
            'total_games': total_games,
            'total_wins': total_wins,
            'total_ties': total_ties,
            'tie_rate': round((total_ties / total_games * 100), 2) if total_games > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': 'Failed to fetch statistics'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'service': 'game-service'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5002, debug=True)
