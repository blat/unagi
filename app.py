from flask import Flask, render_template, request, redirect, flash, Response, session
from unagi.show import Show
from unagi.user import User
from unagi.episode import Episode
from unagi.error import UnagiError

app = Flask(__name__)
app.secret_key = '##SECRET##'

def get_user():
    if 'user' in session:
        return User.load(session['user'])
    return False

app.jinja_env.globals.update(is_past=Episode.is_past)

@app.route("/")
def home():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episodes = user.episodes_ready()
    return render_template('episodes.html', title="My downloads", user=user, episodes=episodes)

@app.route("/processing")
def processing():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episodes = user.episodes_processing()
    return render_template('episodes.html', title="My processing queue", user=user, episodes=episodes)

@app.route("/pending")
def pending():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episodes = user.episodes_pending()
    return render_template('episodes.html', title="My pending queue", user=user, episodes=episodes)

@app.route("/calendar")
def calendar():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episodes = user.episodes_waiting()
    return render_template('episodes.html', title="My agenda", user=user, episodes=episodes)

@app.route('/show/<show_id>')
def show(show_id):
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    show = Show.load(show_id)
    return render_template('episodes.html', user=user, title=show.title, episodes=show.episodes)

@app.route('/subscriptions')
def subscriptions():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    return render_template('shows.html', title="My subscriptions", user=user, shows=user.shows)

@app.route('/explore')
def explore():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    shows = Show.popular(user)
    return render_template('shows.html', title="Explore", user=user, shows=shows)

@app.route('/search')
def search():
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    query = request.args.get('query', '')
    shows = Show.search(query)
    return render_template('shows.html', title="Search", user=user, shows=shows, query=query)

@app.route('/subscribe/<show_id>')
def subscribe(show_id):
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    user.subscribe(show_id)
    return redirect('/subscriptions', code=302)

@app.route('/unsubscribe/<show_id>')
def unsubscribe(show_id):
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    user.unsubscribe(show_id)
    return redirect('/subscriptions', code=302)

@app.route('/queue/<episode_id>')
def queue(episode_id):
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episode = Episode.load(episode_id)
    episode.status = Episode.STATUS_ACTIVE
    try:
        episode.queue()
        return redirect('/processing', code=302)
    except UnagiError as e:
        flash(e.msg)
        return redirect('/pending', code=302)

@app.route('/video/<episode_id>')
def video(episode_id):
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episode = Episode.load(episode_id)
    headers = episode.download_video()
    resp = Response()
    for key in headers:
        resp.headers[key] = headers[key]
    return resp

@app.route('/subtitle/<episode_id>')
def subtitle(episode_id):
    user = get_user()
    if not user:
        return redirect('/login', code=302)
    episode = Episode.load(episode_id)
    headers = episode.download_subtitle()
    resp = Response()
    for key in headers:
        resp.headers[key] = headers[key]
    return resp

@app.route("/login", methods=['GET', 'POST'])
def login():
    if get_user():
        return redirect('/', code=302)
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.auth(email, password)
        if (user):
            session['user'] = user.id
            return redirect('/', code=302)
        flash('Wrong e-mail or password!')
    return render_template('login.html', title="Log-in")

@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect('/', code=302)

if __name__ == "__main__":
    #app.debug = True
    app.threaded = True
    app.run(host='0.0.0.0')
