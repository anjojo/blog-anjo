from flask import Flask, render_template, redirect, url_for, flash, abort
from functools import wraps
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from mysql import MYSQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

# ----------------------------- CONNECT TO DB -----------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = MYSQLAlchemy(app)


# -------------------------------- CONFIGURE LOGIN MANAGER --------------------------------
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------------------- CONFIGURE TABLES -----------------------------
class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    # relationship to blogpost
    posts = relationship("BlogPost", back_populates="author")
    # relationship to comments table
    comments = relationship("Comments", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # relationship to users
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # relationship to comments
    comments = relationship("Comments", back_populates="blog_post")


class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # relationship to blog_posts
    blog_post = relationship("BlogPost", back_populates="comments")
    # relationship to users
    comment_author = relationship("User", back_populates="comments")
    text = db.Column(db.Text(1000), nullable=False)


db.create_all()


# ----------------------------- HELPER AND DECORATOR FUNCTIONS -----------------------------
def create_user(**kwargs):
    new_user = User()
    new_user.email = kwargs['email']
    new_user.password = kwargs['password']
    new_user.name = kwargs['name']
    db.session.add(new_user)
    db.session.commit()
    return new_user


def admin_only(function):
    @wraps(function)
    def wrapper_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return function(*args, **kwargs)
    return wrapper_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # check if email already exists
        if not User.query.filter_by(email=form.email.data).first():
            secure_password = generate_password_hash(form.password.data)
            new_user = create_user(
                email=form.email.data,
                password=secure_password,
                name=form.name.data,
            )
            login_user(new_user)
            return redirect(url_for('get_all_posts', current_user=current_user))
        else:
            flash('Email already exists, login instead.')
            return redirect(url_for('login'))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # check if email exists
        if User.query.filter_by(email=form.email.data).first():
            user = User.query.filter_by(email=form.email.data).first()
            # check if password matches with existing email
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts", current_user=current_user))
            else:
                flash("Incorrect Password.")
                return redirect(url_for('login'))
        else:
            flash("Email does not exist.")
            return redirect(url_for('login'))

    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comments(
                text=form.body.data,
                comment_author=current_user,
                blog_post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("You need to login first before commenting.")
            return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, current_user=current_user, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts", current_user=current_user))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>")
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
