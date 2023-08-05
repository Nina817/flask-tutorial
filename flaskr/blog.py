from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app
)
import os
from flask_paginate import Pagination, get_page_parameter, get_page_args
from werkzeug.exceptions import abort
import sqlite3
from werkzeug.utils import secure_filename

from flaskr.auth import login_required
from flaskr.db import get_db
UPLOAD_FOLDER = 'flaskr/static/file_uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

bp = Blueprint('blog', __name__)
# current_app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER
    
@bp.route('/', methods=('GET', 'POST'))
def index():
    db = get_db()
    total=db.cursor().execute('SELECT count(*) FROM post').fetchone()[0]
    
    # page = request.args.get(get_page_parameter(), type=int, default=1)
    page, per_page, offset = get_page_args(page_parameter="page", per_page_parameter="per_page", per_page=5)
    if request.method == 'POST':
        search = request.form['search']
        posts = db.execute(
            'SELECT p.id, p.title, body, created, author_id, username, count(DISTINCT pl.id) as like_count, group_concat(DISTINCT t.title) as tag_titles'
            ' FROM post p LEFT JOIN user u ON p.author_id = u.id'
            ' LEFT JOIN tagpost tp ON p.id = tp.post_id'
            ' INNER JOIN tag t ON tp.tag_id = t.id  AND t.title like ?'
            ' LEFT JOIN postlikes pl ON p.id = pl.post_id'
            ' GROUP BY p.id, p.title'
            ' ORDER BY created DESC  LIMIT ? OFFSET ?', ('%'+search+'%', 5, offset)).fetchall()
    else: posts = db.execute(
        'SELECT p.id, p.title, body, created, author_id, username, count(DISTINCT pl.id) as like_count, group_concat(DISTINCT t.title) as tag_titles'
        ' FROM post p LEFT JOIN user u ON p.author_id = u.id'
        ' LEFT JOIN tagpost tp ON p.id = tp.post_id'
        ' LEFT JOIN tag t ON tp.tag_id = t.id'
        ' LEFT JOIN postlikes pl ON p.id = pl.post_id'
        ' GROUP BY p.id, p.title'
        ' ORDER BY created DESC LIMIT ? OFFSET ?', (5, offset)).fetchall()
    pagination = Pagination(page=page, total=total, record_name='posts', per_page=5, offset=offset)
    return render_template('blog/index.html', posts=posts, pagination=pagination)


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
    # get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('blog.index'))

@bp.route('/<int:id>/', methods=('POST', 'GET'))
def detail(id):
    db = get_db()
    current_app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER
    if request.method == 'POST':
        post = get_post(id)
        if 'file' not in request.files:
            flash('No file part')
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            db.execute(
                'UPDATE post SET image_path = ?'
                ' WHERE id = ?',
                (filename, id,)
            )
            db.commit()
            file.save(filepath)
    post = get_post(id, check_author=False)
    like = None
    comments =  db.execute('SELECT c.id, body, created, post_id, user_id, u.username'
                            ' FROM comments c LEFT JOIN user u ON c.user_id = u.id' 
                            ' WHERE post_id = ? ORDER BY created DESC', 
                            (id,)).fetchall()
    tags = db.execute('SELECT t.id, t.title, p.id FROM tag t'
                        ' LEFT JOIN tagpost tp ON t.id = tp.tag_id'
                        ' LEFT JOIN post p ON tp.post_id = p.id'
                        ' WHERE p.id = ?',
                        (id,)).fetchall()
    if g.user:
        like = db.execute('SELECT * from postlikes WHERE post_id = ? AND user_id = ?', (id, g.user['id'],)).fetchone()
    like_count = db.execute('SELECT COUNT(*) FROM postlikes WHERE post_id = ?', (id,)).fetchone()
    like_count = like_count[0]
    filepath = db.execute('SELECT image_path from post where id=?', (id,)).fetchone()[0]
    full_filepath = ''
    if filepath:
        full_filepath = '/file_uploads/'+filepath
        print(full_filepath)
    return render_template('blog/detail.html', post=post, like=like, like_count=like_count, comments=comments, tags=tags, post_image=full_filepath)

@bp.route('/<int:id>/like', methods=('POST', 'GET'))
@login_required
def like(id):
    # get_post(id, check_author=False)
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
    # get_post(id, check_author=False)
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

@bp.route('/<int:id>/comment', methods=('POST', 'GET'))
@login_required
def create_comment(id):
    if request.method == 'POST':
        body = request.form['body']
        error = None

        if not body:
            error = 'Your comment is empty.'
        
        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO comments (body, user_id, post_id)'
                ' VALUES (?, ?, ?)',
                (body, g.user['id'], id)
            )
            db.commit()
            return redirect(url_for('blog.detail', id=id))
    return render_template('blog/create_comment.html')

@bp.route('/<int:id>/delete_comment', methods=('POST', 'GET'))
@login_required
def delete_comment(id):
    db = get_db()
    post_id = db.execute('SELECT post_id FROM comments WHERE id = ?', (id,)).fetchone()[0]
    db.execute('DELETE FROM comments WHERE id = ? AND user_id = ?', (id, g.user['id']) )
    db.commit()
    return redirect(url_for('blog.detail', id=post_id))

@bp.route('/<int:id>/create_tag', methods=('POST', 'GET'))
@login_required
def create_tag(id):
    db = get_db()
    error = None
    if request.method == 'POST':
        try:
            get_post(id)
        except:
            error = "You can only add tags to posts you've written"
        print(request.form)
        # print(tag)
        if not request.form.get('tag') and not request.form.get('new_tag'):
            error = 'Please select a tag or create a new one'

        if error is not None:
            flash(error)
        else:
            if request.form.get('tag') != 'none': #old tag
                tag_id = request.form.get('tag')
                duplicates = db.execute('SELECT * from tagpost WHERE tag_id = ? AND post_id = ?', (tag_id, id)).fetchone()
                if duplicates:
                    error = 'This tag has already been applied to this post'
                if error is not None:
                    flash(error)
                else:
                    db.execute(
                            'INSERT INTO tagpost (post_id, tag_id)'
                            ' VALUES (?, ?)',
                            (id, tag_id)
                        )
                    db.commit()
                    return redirect(url_for('blog.detail', id=id))
            
            if request.form.get('new_tag'):
                new_tag = request.form['new_tag']
                print(new_tag)
                duplicates = db.execute('SELECT * from tag WHERE title = ?', (new_tag,)).fetchone()
                if duplicates:
                    error = 'There is already a tag of this name.'
                if error is not None:
                    flash(error)
                else:
                    print(new_tag)
                    db.execute(
                        'INSERT INTO tag (title)'
                        ' VALUES (?)',
                        (new_tag,)
                    )
                    tag_id = db.execute("SELECT id FROM tag WHERE title =?", (new_tag, )).fetchone()
                    print(tag_id[0])
                    db.execute(
                        'INSERT INTO tagpost (post_id, tag_id)'
                        ' VALUES (?, ?)',
                        (id, tag_id[0])
                    )
                    db.commit()
            
                return redirect(url_for('blog.detail', id=id))
    tags = db.execute("SELECT * from tag").fetchall()
    return render_template('blog/create_tag.html', tags=tags)

@bp.route('/<int:id>/update_tag', methods=('GET', 'POST'))
@login_required
def update_tag(id):
    # post = get_post(id)
    db = get_db()
    tag = db.execute('SELECT * from tag WHERE id= ?', (id,)).fetchone()
    post_id = db.execute('SELECT post_id from tagpost WHERE tag_id= ?', (id,)).fetchone()
    if request.method == 'POST':
        title = request.form['title']
        error = None

        if not title:
            error = 'Title is required.'
        
        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE tag SET title = ?'
                ' WHERE id = ?',
                (title, id)
            )
            db.commit()
            return redirect(url_for('blog.detail', id=post_id[0]))
    return render_template('blog/update_tag.html', tag=tag)

@bp.route('/<int:id>/delete_tag', methods=('POST', 'GET'))
@login_required
def delete_tag(id):
    # get_post(id)
    db = get_db()
    post_id = db.execute('SELECT post_id FROM tagpost WHERE tag_id = ?', (id,)).fetchone()[0]
    db.execute('DELETE FROM tagpost WHERE post_id = ? AND tag_id = ?', (post_id, id,))
    db.commit()
    return redirect(url_for('blog.detail', id=post_id))

# @bp.route('/new_search', methods=('POST', 'GET'))
# def new_search():
#     db= get_db()
    
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
