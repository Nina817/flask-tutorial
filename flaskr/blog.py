from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

bp = Blueprint('blog', __name__)

@bp.route('/')
def index():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, title, body, created, author_id, username, count(pl.id)'
        ' FROM post p JOIN user u ON p.author_id = u.id'
        ' LEFT JOIN postlikes pl ON p.id = pl.post_id'
        ' GROUP BY p.id'
        ' ORDER BY created DESC'
    ).fetchall()
    for row in posts:
        print(row['title'])
    return render_template('blog/index.html', posts=posts)

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'
        
        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO post (title, body, author_id)'
                ' VALUES (?, ?, ?)',
                (title, body, g.user['id'])
            )
            db.commit()
            return redirect(url_for('blog.index'))
    return render_template('blog/create.html')

def get_post(id, check_author=True):
    post = get_db().execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM post p JOIN user u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")
    
    if check_author and post['author_id'] != g.user['id']:
        abort(403)
    
    return post

@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'
        
        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET title = ?, body = ?'
                ' WHERE id = ?',
                (title, body, id)
            )
            db.commit()
            return redirect(url_for('blog.index'))
    return render_template('blog/update.html', post=post)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('blog.index'))

@bp.route('/<int:id>/')
def detail(id):
    post = get_post(id, check_author=False)
    db = get_db()
    like = None
    if g.user:
        like = db.execute('SELECT * from postlikes WHERE post_id = ? AND user_id = ?', (id, g.user['id'],)).fetchone()
    like_count = db.execute('SELECT COUNT(*) FROM postlikes WHERE post_id = ?', (id,)).fetchone()
    like_count = like_count[0]
    return render_template('blog/detail.html', post=post, like=like, like_count=like_count)

@bp.route('/<int:id>/like', methods=('POST', 'GET'))
@login_required
def like(id):
    get_post(id, check_author=False)
    db = get_db()
    likes = db.execute('SELECT * from postlikes WHERE post_id = ? AND user_id = ?', (id, g.user['id'])).fetchone()
    error = None
    if likes:
        error = 'You have already liked this post.'
    
    if error is not None:
        flash(error)
    else:
        db.execute(
                'INSERT INTO postlikes (user_id, post_id)'
                ' VALUES (?, ?)',
                (g.user['id'], id)
        )
        db.commit()
    return redirect(url_for('blog.detail', id=id))

@bp.route('/<int:id>/unlike', methods=('POST', 'GET'))
@login_required
def unlike(id):
    get_post(id, check_author=False)
    db = get_db()
    likes = db.execute('SELECT * from postlikes WHERE post_id = ? AND user_id = ?', (id, g.user['id'])).fetchone()
    error = None
    if not likes:
        error = "You have already unliked this post."
    
    if error is not None:
        flash(error)
    else:
        db.execute(
                'DELETE FROM postlikes WHERE user_id=? AND post_id=?',
                (g.user['id'], id)
        )
        db.commit()
    return redirect(url_for('blog.detail', id=id))
